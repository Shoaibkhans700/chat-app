pipeline {

    agent any

    environment {
        DOCKERHUB      = 'shoaib3'
        BACKEND_REPO   = 'chat-backend'
        FRONTEND_REPO  = 'chat-frontend'
    }

    stages {

        // =========================================================
        // CHECKOUT
        // =========================================================
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


        // =========================================================
        // PYTHON UNIT TEST
        // =========================================================
        stage('Backend Unit Test') {

            agent {
                docker {
                    image 'shoaib3/python-agent:latest'
                }
            }

            steps {
                dir('backend') {

                    sh '''
                        set -e

                        echo "=============================="
                        echo "Python Version"
                        echo "=============================="

                        python3 --version

                        python3 -m venv .venv
                        . .venv/bin/activate

                        pip install --quiet -r requirements.txt
                        pip install --quiet pytest httpx

                        echo "=============================="
                        echo "Running Unit Tests"
                        echo "=============================="

                        pytest -v
                    '''
                }
            }
        }


        // =========================================================
        // TEST SONARQUBE NETWORK
        // =========================================================
        stage('Test Sonar Network') {

            steps {

                sh '''
                    set -e

                    echo "=============================="
                    echo "Testing SonarQube Network"
                    echo "=============================="

                    curl -f \
                      --connect-timeout 10 \
                      http://13.203.154.220:9000/api/system/status

                    echo ""
                    echo "SonarQube network connection SUCCESS"
                '''
            }
        }


        // =========================================================
        // TEST SONARQUBE TOKEN
        // =========================================================
        stage('Test Sonar Authentication') {

            steps {

                withCredentials([
                    string(
                        credentialsId: 'sonar-cred',
                        variable: 'SONAR_TOKEN'
                    )
                ]) {

                    sh '''
                        set -e

                        echo "=============================="
                        echo "Testing SonarQube Authentication"
                        echo "=============================="

                        if [ -z "$SONAR_TOKEN" ]; then
                            echo "ERROR: SONAR_TOKEN is empty"
                            exit 1
                        fi

                        echo "Token available: YES"

                        curl -f \
                          -u "$SONAR_TOKEN:" \
                          http://13.203.154.220:9000/api/v2/analysis/version

                        echo ""
                        echo "SonarQube authentication SUCCESS"
                    '''
                }
            }
        }


        // =========================================================
        // SONARQUBE ANALYSIS
        // =========================================================
        stage('SonarQube Analysis') {

            steps {

                withSonarQubeEnv('sonarqube') {

                    script {

                        def scannerHome = tool 'sonar-scanner'

                        sh """
                            set -e

                            echo "=============================="
                            echo "SonarQube Code Analysis"
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


        // =========================================================
        // SONARQUBE QUALITY GATE
        // =========================================================
        stage('SonarQube Quality Gate') {

            steps {

                timeout(time: 5, unit: 'MINUTES') {

                    waitForQualityGate abortPipeline: true
                }
            }
        }


        // =========================================================
        // BUILD DOCKER IMAGES
        // =========================================================
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
                        '''
                    }
                }
            }
        }


        // =========================================================
        // TRIVY SECURITY SCAN
        // =========================================================
        stage('Trivy Security Scan') {

            steps {

                sh '''
                    set -e

                    echo "=============================="
                    echo "Backend Security Scan"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}


                    echo "=============================="
                    echo "Frontend Security Scan"
                    echo "=============================="

                    trivy image \
                      --severity HIGH,CRITICAL \
                      --exit-code 0 \
                      ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}
                '''
            }
        }


        // =========================================================
        // PUSH TO DOCKER HUB
        // =========================================================
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
                        set -e

                        echo "=============================="
                        echo "Docker Hub Login"
                        echo "=============================="

                        echo "$DOCKER_PASSWORD" | docker login \
                          --username "$DOCKER_USERNAME" \
                          --password-stdin


                        echo "=============================="
                        echo "Push Backend"
                        echo "=============================="

                        docker push \
                          ${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}


                        echo "=============================="
                        echo "Push Frontend"
                        echo "=============================="

                        docker push \
                          ${DOCKERHUB}/${FRONTEND_REPO}:${IMAGE_TAG}


                        docker logout
                    '''
                }
            }
        }
    }


    // =============================================================
    // POST
    // =============================================================
    post {

        always {

            sh 'docker image prune -f || true'
        }


        success {

            echo """
==========================================
       CHAT APP PIPELINE SUCCESS
==========================================

IMAGE TAG:
${IMAGE_TAG}

BACKEND:
${DOCKERHUB}/${BACKEND_REPO}:${IMAGE_TAG}

FRONTEND:
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
