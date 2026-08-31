pipeline {

    agent any

    environment {
        DOCKERHUB      = 'shoaib3'
        BACKEND_REPO   = 'chat-backend'
        FRONTEND_REPO  = 'chat-frontend'
        PYTHON_REPO    = 'python-agent'

        GITOPS_REPO    = 'https://github.com/Shoaibkhans700/chat-app-k8-manifest.git'
        GITOPS_BRANCH  = 'main'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm

                script {
                    env.IMAGE_TAG = "v${BUILD_NUMBER}"

                    echo "Image Tag: ${env.IMAGE_TAG}"
                }
            }
        }

        stage('Backend Unit Test') {

            agent {
                docker {
                    image 'shoaib3/python-agent:latest'
                    reuseNode true
                }
            }

            steps {
                dir('backend') {
                    sh '''
                        set -e

                        python3 --version

                        python3 -m venv .venv
                        . .venv/bin/activate

                        pip install --quiet -r requirements.txt
                        pip install --quiet pytest httpx

                        pytest -v
                    '''
                }
            }
        }

        stage('Test Sonar Authentication') {
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        set -e

                        echo "Testing SonarQube..."

                        curl -u "$SONAR_AUTH_TOKEN:" \
                          http://65.0.6.193:9000/api/v2/analysis/version

                        echo "SonarQube authentication successful"
                    '''
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {

                withSonarQubeEnv('sonarqube') {

                    script {
                        def scannerHome = tool 'sonar-scanner'

                        sh """
                            set -e

                            echo "Running SonarQube Analysis"

                            ${scannerHome}/bin/sonar-scanner \
                              -Dsonar.projectKey=chat-app \
                              -Dsonar.projectName=chat-app \
                              -Dsonar.sources=backend,frontend \
                              -Dsonar.sourceEncoding=UTF-8
                        """
                    }
                }
            }
        }

        stage('SonarQube Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Docker Images') {

            parallel {

                stage('Backend Image') {
                    steps {
                        sh '''
                            set -e

                            docker build \
                              -t ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG} \
                              ./backend
                        '''
                    }
                }

                stage('Frontend Image') {
                    steps {
                        sh '''
                            set -e

                            docker build \
                              -t ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG} \
                              ./frontend
                        '''
                    }
                }
            }
        }

        stage('Trivy Security Scan') {
            steps {
                sh '''
                    set -e

                    echo "Scanning Backend Image..."

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

                    echo "Scanning Frontend Image..."

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push Application Images') {
            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'docker-cred',
                        usernameVariable: 'DOCKER_USERNAME',
                        passwordVariable: 'DOCKER_PASSWORD'
                    )
                ]) {

                    sh '''
                        set -e

                        echo "$DOCKER_PASSWORD" | docker login \
                          --username "$DOCKER_USERNAME" \
                          --password-stdin

                        docker push \
                          ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

                        docker push \
                          ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}

                        docker logout
                    '''
                }
            }
        }

        stage('Tag Python Agent') {
            steps {
                sh '''
                    set -e

                    docker pull \
                      ${DOCKERHUB}/${PYTHON_REPO}:latest

                    docker tag \
                      ${DOCKERHUB}/${PYTHON_REPO}:latest \
                      ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Scan Python Agent') {
            steps {
                sh '''
                    set -e

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push Python Agent') {
            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'docker-cred',
                        usernameVariable: 'DOCKER_USERNAME',
                        passwordVariable: 'DOCKER_PASSWORD'
                    )
                ]) {

                    sh '''
                        set -e

                        echo "$DOCKER_PASSWORD" | docker login \
                          --username "$DOCKER_USERNAME" \
                          --password-stdin

                        docker push \
                          ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}

                        docker logout
                    '''
                }
            }
        }

        stage('Update GitOps Repository') {
            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'github-cred',
                        usernameVariable: 'GITHUB_USERNAME',
                        passwordVariable: 'GITHUB_TOKEN'
                    )
                ]) {

                    sh '''
                        set -e

                        rm -rf gitops-repo

                        git clone \
                          https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/Shoaibkhans700/chat-app-k8-manifest.git \
                          gitops-repo

                        cd gitops-repo

                        sed -i \
                          "s|image: shoaib3/chat-backend:.*|image: shoaib3/chat-backend:${IMAGE_TAG}|g" \
                          backend-deployment.yaml

                        sed -i \
                          "s|image: shoaib3/chat-frontend:.*|image: shoaib3/chat-frontend:${IMAGE_TAG}|g" \
                          frontend-deployment.yaml

                        echo "Updated images:"
                        grep "image:" backend-deployment.yaml
                        grep "image:" frontend-deployment.yaml

                        git config user.name "Jenkins"
                        git config user.email "jenkins@localhost"

                        git add \
                          backend-deployment.yaml \
                          frontend-deployment.yaml

                        if git diff --cached --quiet; then
                            echo "No image changes detected."
                        else
                            git commit -m "Update images to ${IMAGE_TAG}"
                            git push origin ${GITOPS_BRANCH}
                        fi

                        cd ..

                        rm -rf gitops-repo
                    '''
                }
            }
        }
    }

    post {

        always {
            sh 'docker image prune -f || true'
        }

        success {
            echo """
==========================================
       CHAT APP PIPELINE SUCCESS
==========================================

Backend:
${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

Frontend:
${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}

Python Agent:
${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}

GitOps:
${GITOPS_REPO}

ArgoCD will sync the GitOps changes.

==========================================
"""
        }

        failure {
            echo """
==========================================
       CHAT APP PIPELINE FAILED
==========================================

Build Number:
${BUILD_NUMBER}

Image Tag:
${IMAGE_TAG}

Check the failed stage.

==========================================
"""
        }
    }
}
