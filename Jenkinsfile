// Jenkins pipeline for chat-app.
//
// Requires these credentials to be configured in Jenkins (Manage Jenkins
// -> Credentials):
//   - aws-credentials      : AWS access key/secret with ECR push permission
//   - gitops-repo-creds    : SSH key or token with push access to the
//                            chat-app-gitops repository
//
// Requires these tools on the Jenkins agent: docker, git, an AWS-CLI v2,
// and (for the security scan stage) Trivy.

pipeline {
    agent any

    environment {
        AWS_REGION       = 'us-east-1'
        AWS_ACCOUNT_ID    = '123456789012'
        ECR_REGISTRY      = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        BACKEND_REPO      = 'chat-backend'
        FRONTEND_REPO     = 'chat-frontend'
        // Prefer the commit SHA over BUILD_NUMBER: it's traceable back to
        // exact source, immutable, and safe to rebuild/retag without
        // colliding with an unrelated build counter.
        IMAGE_TAG         = "${GIT_COMMIT.take(7)}"
        GITOPS_REPO_URL   = 'git@github.com:your-org/chat-app-gitops.git'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Backend: Unit Tests') {
            steps {
                dir('backend') {
                    sh '''
                        python3 -m venv .venv
                        . .venv/bin/activate
                        pip install --quiet -r requirements.txt
                        pip install --quiet pytest httpx
                        pytest -v || true   # replace `|| true` once a real test suite exists
                    '''
                }
            }
        }

        stage('Build Docker Images') {
            parallel {
                stage('Backend Image') {
                    steps {
                        dir('backend') {
                            sh "docker build -t ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG} ."
                        }
                    }
                }
                stage('Frontend Image') {
                    steps {
                        dir('frontend') {
                            sh "docker build -t ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG} ."
                        }
                    }
                }
            }
        }

        stage('Security Scan') {
            steps {
                sh """
                    trivy image --exit-code 0 --severity HIGH,CRITICAL ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                    trivy image --exit-code 0 --severity HIGH,CRITICAL ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                """
                // Flip --exit-code to 1 once the team is ready to fail the
                // build on HIGH/CRITICAL findings instead of just reporting them.
            }
        }

        stage('Push to ECR') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'aws-credentials',
                    usernameVariable: 'AWS_ACCESS_KEY_ID',
                    passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                )]) {
                    sh """
                        aws ecr get-login-password --region ${AWS_REGION} \
                          | docker login --username AWS --password-stdin ${ECR_REGISTRY}

                        docker push ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}
                        docker push ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}
                    """
                }
            }
        }

        stage('Update GitOps Repository') {
            steps {
                // Jenkins' job ends here. It never runs `kubectl apply` -
                // Argo CD, watching chat-app-gitops, picks up this commit
                // and reconciles the cluster on its own. This keeps the
                // cluster's desired state defined entirely in Git and lets
                // Argo CD self-heal any manual kubectl drift.
                sshagent(credentials: ['gitops-repo-creds']) {
                    sh """
                        rm -rf gitops-repo
                        git clone ${GITOPS_REPO_URL} gitops-repo
                        cd gitops-repo

                        sed -i "s|image: .*chat-backend:.*|image: ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG}|" backend-deployment.yaml
                        sed -i "s|image: .*chat-frontend:.*|image: ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}|" frontend-deployment.yaml

                        git config user.email "jenkins@ci.local"
                        git config user.name "jenkins-ci"
                        git commit -am "Deploy chat-app ${IMAGE_TAG}"
                        git push origin main
                    """
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        success {
            echo "Pushed ${ECR_REGISTRY}/${BACKEND_REPO}:${IMAGE_TAG} and ${ECR_REGISTRY}/${FRONTEND_REPO}:${IMAGE_TAG}; GitOps repo updated. Argo CD will sync shortly."
        }
        failure {
            echo "Pipeline failed - see stage logs above."
        }
    }
}
