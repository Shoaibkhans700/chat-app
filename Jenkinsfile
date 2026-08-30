pipeline {

    agent any

    environment {
        DOCKERHUB      = 'shoaib3'
        BACKEND_REPO   = 'chat-backend'
        FRONTEND_REPO  = 'chat-frontend'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm

                script {
                    env.IMAGE_TAG = sh(
                        script: 'git rev-parse --short=7 HEAD',
                        returnStdout: true
                    ).trim()

                    echo "Image Tag: ${env.IMAGE_TAG}"
                }
            }
        }

        stage('Backend Unit Test') {

            agent {
                docker {
                    image 'shoaib3/python-agent:latest'
                }
            }

            steps {
                dir('backend') {
                    sh '''
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
                echo "Testing SonarQube..."
                curl -u "$SONAR_AUTH_TOKEN:" \
                    http://13.204.67.149:9000/api/v2/analysis/version
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
                            docker build \
                              -t ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG} \
                              ./backend
                        '''
                    }
                }

                stage('Frontend Image') {
                    steps {
                        sh '''
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
                    echo "=============================="
                    echo "Scanning Backend Image"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}


                    echo "=============================="
                    echo "Scanning Frontend Image"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push to Docker Hub') {

            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'docker-cred',
                        usernameVariable: 'DOCKER_USERNAME',
                        passwordVariable: 'DOCKER_PASSWORD'
                    )
                ]) {

                    sh '''
                        echo "$DOCKER_PASSWORD" | docker login \
                          --username "$DOCKER_USERNAME" \
                          --password-stdin

                        echo "Pushing Backend Image..."

                        docker push \
                          ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

                        echo "Pushing Frontend Image..."

                        docker push \
                          ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}

                        docker logout
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

==========================================
"""
        }

        failure {
            echo """
==========================================
       CHAT APP PIPELINE FAILED
==========================================

Check the failed stage above.

==========================================
"""
        }
    }
}
