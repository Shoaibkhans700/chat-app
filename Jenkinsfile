pipeline {

    agent {
        docker {
            image 'shoaib3/python-agent:latest'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
            reuseNode true
        }
    }

    environment {
        DOCKERHUB      = 'shoaib3'

        BACKEND_REPO  = 'chat-backend'
        FRONTEND_REPO = 'chat-frontend'
        PYTHON_REPO   = 'python-agent'

        GITOPS_REPO   = 'https://github.com/Shoaibkhans700/chat-app-k8-manifest.git'
        GITOPS_BRANCH = 'main'
    }

    stages {

        // =====================================================
        // CHECKOUT
        // =====================================================
        stage('Checkout') {
            steps {

                checkout scm

                script {
                    env.IMAGE_TAG = "v${BUILD_NUMBER}"

                    echo "=========================================="
                    echo "Build Number : ${BUILD_NUMBER}"
                    echo "Image Tag    : ${IMAGE_TAG}"
                    echo "=========================================="
                }
            }
        }


        // =====================================================
        // CHECK AGENT TOOLS
        // =====================================================
        stage('Check Agent Tools') {
            steps {
                sh '''
                    set -e

                    echo "Python:"
                    python3 --version

                    echo "Git:"
                    git --version

                    echo "Docker:"
                    docker --version

                    echo "Trivy:"
                    trivy --version

                    echo "Curl:"
                    curl --version | head -1
                '''
            }
        }


        // =====================================================
        // BACKEND UNIT TEST
        // =====================================================
        stage('Backend Unit Test') {
            steps {

                dir('backend') {

                    sh '''
                        set -e

                        echo "Installing backend dependencies..."

                        python3 -m venv .venv

                        . .venv/bin/activate

                        pip install --quiet -r requirements.txt
                        pip install --quiet pytest httpx

                        echo "Running backend tests..."

                        pytest -v
                    '''
                }
            }
        }


        // =====================================================
        // SONARQUBE AUTHENTICATION
        // =====================================================
        stage('Test Sonar Authentication') {
            steps {

                withSonarQubeEnv('sonarqube') {

                    sh '''
                        set -e

                        echo "=============================="
                        echo "Testing SonarQube"
                        echo "=============================="

                        curl -u "$SONAR_AUTH_TOKEN:" \
                          http://65.0.6.193:9000/api/v2/analysis/version

                        echo ""
                        echo "SonarQube authentication successful."
                    '''
                }
            }
        }


        // =====================================================
        // SONARQUBE ANALYSIS
        // =====================================================
        stage('SonarQube Analysis') {
            steps {

                withSonarQubeEnv('sonarqube') {

                    script {

                        def scannerHome = tool 'sonar-scanner'

                        sh """
                            set -e

                            echo "=============================="
                            echo "Running SonarQube Analysis"
                            echo "=============================="

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


        // =====================================================
        // SONARQUBE QUALITY GATE
        // =====================================================
        stage('SonarQube Quality Gate') {
            steps {

                timeout(time: 5, unit: 'MINUTES') {

                    waitForQualityGate abortPipeline: true
                }
            }
        }


        // =====================================================
        // BUILD APPLICATION IMAGES
        // =====================================================
        stage('Build Docker Images') {

            parallel {

                stage('Backend Image') {
                    steps {

                        sh '''
                            set -e

                            echo "Building Backend Image..."

                            docker build \
                              -t ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG} \
                              ./backend

                            echo "Created:"
                            echo "${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}"
                        '''
                    }
                }


                stage('Frontend Image') {
                    steps {

                        sh '''
                            set -e

                            echo "Building Frontend Image..."

                            docker build \
                              -t ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG} \
                              ./frontend

                            echo "Created:"
                            echo "${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}"
                        '''
                    }
                }
            }
        }


        // =====================================================
        // TRIVY APPLICATION SCAN
        // =====================================================
        stage('Trivy Security Scan') {
            steps {

                sh '''
                    set -e

                    echo "=============================="
                    echo "Scanning Backend"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}


                    echo "=============================="
                    echo "Scanning Frontend"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =====================================================
        // PUSH APPLICATION IMAGES
        // =====================================================
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

                        echo "Pushing Backend..."

                        docker push \
                          ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

                        echo "Pushing Frontend..."

                        docker push \
                          ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}

                        docker logout
                    '''
                }
            }
        }


        // =====================================================
        // TAG PYTHON AGENT
        // =====================================================
        stage('Tag Python Agent') {
            steps {

                sh '''
                    set -e

                    echo "=========================================="
                    echo "Tagging Python Agent"
                    echo "=========================================="

                    docker pull \
                      ${DOCKERHUB}/${PYTHON_REPO}:latest

                    docker tag \
                      ${DOCKERHUB}/${PYTHON_REPO}:latest \
                      ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}

                    echo "Python Agent:"
                    echo "${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}"
                '''
            }
        }


        // =====================================================
        // TRIVY PYTHON AGENT
        // =====================================================
        stage('Scan Python Agent') {
            steps {

                sh '''
                    set -e

                    echo "=========================================="
                    echo "Scanning Python Agent"
                    echo "=========================================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =====================================================
        // PUSH PYTHON AGENT
        // =====================================================
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

                        echo "Pushing Python Agent..."

                        docker push \
                          ${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}

                        docker logout

                        echo "Python Agent pushed:"
                        echo "${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}"
                    '''
                }
            }
        }


        // =====================================================
        // UPDATE GITOPS REPOSITORY
        // =====================================================
        stage('Update GitOps Image Tags') {
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

                        echo "=========================================="
                        echo "Updating GitOps Repository"
                        echo "=========================================="


                        rm -rf gitops-repo


                        git clone \
                          https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/Shoaibkhans700/chat-app-k8-manifest.git \
                          gitops-repo


                        cd gitops-repo


                        echo "Current Backend Image:"
                        grep "image:" backend-deployment.yaml || true

                        echo "Current Frontend Image:"
                        grep "image:" frontend-deployment.yaml || true


                        echo "Updating Backend Image..."

                        sed -i \
                          "s|image: shoaib3/chat-backend:.*|image: shoaib3/chat-backend:${IMAGE_TAG}|g" \
                          backend-deployment.yaml


                        echo "Updating Frontend Image..."

                        sed -i \
                          "s|image: shoaib3/chat-frontend:.*|image: shoaib3/chat-frontend:${IMAGE_TAG}|g" \
                          frontend-deployment.yaml


                        echo "=========================================="
                        echo "New Images"
                        echo "=========================================="

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

                            git commit \
                              -m "Update images to ${IMAGE_TAG}"

                            git push origin ${GITOPS_BRANCH}

                        fi


                        cd ..

                        rm -rf gitops-repo
                    '''
                }
            }
        }
    }


    // =========================================================
    // POST
    // =========================================================
    post {

        always {

            sh '''
                docker image prune -f || true
            '''
        }


        success {

            echo """
==========================================
       CHAT APP PIPELINE SUCCESS
==========================================

Build Number:
${BUILD_NUMBER}

Image Tag:
${IMAGE_TAG}

Backend:
${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

Frontend:
${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}

Python Agent:
${DOCKERHUB}/${PYTHON_REPO}:${IMAGE_TAG}

GitOps:
${GITOPS_REPO}

==========================================
       ARGOCD WILL SYNC THE CHANGES
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

Check the failed stage above.

==========================================
"""
        }
    }
}
