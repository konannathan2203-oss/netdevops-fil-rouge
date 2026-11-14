// Pipeline CI/CD NetDevOps - projet fil rouge
// Etapes : Checkout, Lint, SonarQube, Build Docker, Trivy, Deploiement test,
//          Tests de connectivite, Deploiement prod, Notification.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
        timeout(time: 60, unit: 'MINUTES')
    }

    triggers {
        // La VM n'est pas joignable depuis GitHub : Jenkins interroge le depot
        pollSCM('H/5 * * * *')
    }

    parameters {
        booleanParam(name: 'DEPLOY_PROD', defaultValue: true,
                     description: 'Deployer en production si tous les tests passent (branche main uniquement)')
        booleanParam(name: 'TRIVY_FAIL_ON_CRITICAL', defaultValue: true,
                     description: 'Bloquer le pipeline si une CVE CRITIQUE corrigeable est detectee')
        string(name: 'NOTIFY_EMAIL', defaultValue: '',
               description: 'Adresse a prevenir en cas d echec (vide = pas d email)')
    }

    environment {
        IMAGE_TAG              = "${env.BUILD_NUMBER}"
        IMAGES                 = 'router-fw web-dmz dns-lan client'
        TRIVY_IMAGE            = 'aquasec/trivy:0.69.3'
        SONAR_SCANNER_IMAGE    = 'sonarsource/sonar-scanner-cli:11'
        SONAR_HOST_URL         = 'http://localhost:9000'
        ANSIBLE_VAULT_PASSWORD = credentials('ansible-vault-pass')
        VAULT_OPTS             = '--vault-password-file scripts/vault_pass.sh'
        ANSIBLE_FORCE_COLOR    = '0'
    }

    stages {
        stage('1. Checkout') {
            steps {
                checkout scm
                sh 'git log -1 --oneline'
                sh 'chmod +x scripts/*.sh tests/*.py docker/*/*.sh docker/common/*.sh'
                sh 'mkdir -p reports'
            }
        }

        stage('2. Lint') {
            steps {
                sh 'yamllint .'
                sh 'ansible-lint playbooks/ roles/'
                sh 'pylint tests/'
                sh 'shellcheck scripts/*.sh docker/*/*.sh docker/common/*.sh'
            }
        }

        stage('3. SonarQube Scan') {
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh '''
                        docker run --rm --network host \
                          -u "$(id -u):$(id -g)" \
                          -e SONAR_HOST_URL="$SONAR_HOST_URL" \
                          -e SONAR_TOKEN="$SONAR_TOKEN" \
                          -e SONAR_USER_HOME=/usr/src/.sonar-cache \
                          -v "$WORKSPACE:/usr/src" \
                          "$SONAR_SCANNER_IMAGE"
                    '''
                }
            }
        }

        stage('4. Build Docker') {
            steps {
                sh 'ansible-playbook -i inventories/test playbooks/site.yml --tags render,build -e image_tag=$IMAGE_TAG $VAULT_OPTS'
                sh 'docker images "netdevops/*"'
            }
        }

        stage('5. Trivy Scan') {
            steps {
                sh '''
                    FAIL=0
                    for img in $IMAGES; do
                      echo "=== Analyse de netdevops/$img:$IMAGE_TAG ==="
                      docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v trivy-cache:/root/.cache \
                        -v "$WORKSPACE/reports:/reports" \
                        "$TRIVY_IMAGE" image --scanners vuln --severity HIGH,CRITICAL \
                        --format table --output "/reports/trivy-$img.txt" "netdevops/$img:$IMAGE_TAG"
                      cat "reports/trivy-$img.txt"
                      docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        -v trivy-cache:/root/.cache \
                        "$TRIVY_IMAGE" image --scanners vuln --severity CRITICAL --ignore-unfixed \
                        --exit-code 1 --quiet "netdevops/$img:$IMAGE_TAG" || FAIL=1
                    done
                    docker run --rm -v "$WORKSPACE/reports:/r" alpine:3.22 chown -R "$(id -u):$(id -g)" /r
                    if [ "$FAIL" = "1" ] && [ "$TRIVY_FAIL_ON_CRITICAL" = "true" ]; then
                      echo "CVE CRITIQUE corrigeable detectee : pipeline bloque"
                      exit 1
                    fi
                '''
            }
        }

        stage('6. Deploiement Test') {
            steps {
                sh 'ansible-playbook -i inventories/test playbooks/site.yml --tags render,deploy -e image_tag=$IMAGE_TAG $VAULT_OPTS'
            }
        }

        stage('7. Tests de connectivite') {
            steps {
                sh 'python3 tests/connectivity_test.py --env test --junit reports/connectivity-test.xml'
                sh 'docker exec test-router-fw nft list ruleset > reports/nftables-test.txt'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/connectivity-test.xml'
                    // L'environnement de test est supprime pour liberer la memoire
                    sh 'ansible-playbook -i inventories/test playbooks/destroy.yml $VAULT_OPTS || true'
                }
            }
        }

        stage('8. Deploiement Prod') {
            when {
                allOf {
                    expression { params.DEPLOY_PROD }
                    expression { (env.GIT_BRANCH ?: '') ==~ /(origin\/)?main/ }
                }
            }
            steps {
                sh 'ansible-playbook -i inventories/prod playbooks/site.yml --tags render,deploy -e image_tag=$IMAGE_TAG $VAULT_OPTS'
                sh 'python3 tests/connectivity_test.py --env prod --junit reports/connectivity-prod.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/connectivity-prod.xml'
                }
            }
        }
    }

    // 9. Notification
    post {
        always {
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        success {
            echo "Pipeline reussi - images netdevops/*:${env.IMAGE_TAG}"
        }
        failure {
            echo "ECHEC du pipeline ${env.JOB_NAME} #${env.BUILD_NUMBER} : ${env.BUILD_URL}"
            script {
                if (params.NOTIFY_EMAIL?.trim()) {
                    try {
                        mail to: params.NOTIFY_EMAIL,
                             subject: "[NetDevOps] Echec du pipeline ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                             body: "Le pipeline a echoue.\nDetails : ${env.BUILD_URL}console"
                    } catch (err) {
                        echo "Email non envoye (SMTP non configure ?) : ${err}"
                    }
                }
            }
        }
    }
}
