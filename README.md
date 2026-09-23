# Medical Shop – DevOps / CI-CD Project

This repository is the DevOps layer for the supplied **Product Expiry Alert System for Medical Shop** Flask application.

## What was matched to the supplied application

- Python Flask application (`app.py`)
- Flask-MySQLdb + MySQL 8
- `product_expiry_db` database
- Existing `templates/` and `static/` directories are preserved
- Flask-WeasyPrint PDF support is included in the Linux image
- SMTP expiry-alert settings are now read from environment variables instead of being hard-coded
- `/health` endpoint is provided for Kubernetes probes
- `/metrics` is provided by `prometheus-flask-exporter`
- The Docker container initializes the existing database schema before starting Gunicorn

> **Important:** the original application contained an SMTP app password in `app.py`. It has intentionally been removed from the DevOps-ready copy. Rotate that credential if it was ever committed to a public or shared repository.

## Architecture

```text
                         Internet
                            |
                         Ingress
                            |
                    +-------v-------+
                    | Flask Service |
                    +-------+-------+
                            |
                 +----------+----------+
                 | Flask/Gunicorn Pods |
                 | HTML + API + PDF    |
                 +----------+----------+
                            |
                       MySQL Service
                            |
                       MySQL 8 PVC

       Prometheus <---- /metrics ---- Flask Pods
           |
        Grafana

GitHub Actions -> Docker Hub -> EKS -> Kubernetes
Terraform --------------------^ 
Ansible -> Linux operations/deployment host
```

The application is logically three-tier (presentation/templates, Flask application, MySQL database), while the supplied Flask code serves the presentation and application layers from the same container.

## Directory structure

```text
Medical Shop/
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── ansible/
│   ├── inventory.ini
│   ├── playbook.yml
│   └── roles/
│       └── common/
│           └── tasks/
│               └── main.yml
├── k8s/
│   ├── namespace.yml
│   ├── deployment.yml
│   ├── service.yml
│   ├── configmap.yml
│   ├── secret.yml
│   ├── mysql.yml
│   ├── mysql-secret.yml
│   ├── mysql-init-configmap.yml
│   ├── expiry-cronjob.yml
│   └── ingress.yml
├── monitering/
│   ├── prometheus.yml
│   ├── prometheus-rbac.yml
│   ├── prometheus-deployment.yml
│   ├── prometheus-service.yml
│   └── grafana/
│       ├── configmap.yml
│       ├── secret.yml
│       ├── deployment.yml
│       ├── service.yml
│       └── ingress.yml
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   └── terraform.tfwars
├── app.py
├── config.py
├── database.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
├── .dockerignore
├── .gitignore
├── pom.xml
└── README.md
```

## 1. Run locally with Docker

Create a local `.env` file (do not commit it):

```env
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
MYSQL_DB=product_expiry_db
SECRET_KEY=replace-with-a-long-random-value
MAIL_USERNAME=your-smtp-user
MAIL_PASSWORD=your-smtp-app-password
MAIL_RECIPIENTS=recipient@example.com
```

For local Docker testing, use the included Compose file:

```bash
docker compose up --build
```

Open `http://localhost:5000`. The image listens on port `5000` and initializes the same MySQL schema used by the application.

## 2. GitHub Actions CI/CD

The workflow has three stages:

1. **Validate** – Python dependency installation, compile check, Maven package and Kubernetes YAML parsing.
2. **Docker** – Build and push the image to Docker Hub.
3. **Deploy** – Authenticate to AWS, configure `kubectl` for EKS, create secrets, apply Kubernetes manifests, update the image and wait for rollout.

### Required GitHub Actions secrets

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
EKS_CLUSTER_NAME
MYSQL_PASSWORD
SECRET_KEY
MAIL_USERNAME
MAIL_PASSWORD
MAIL_RECIPIENTS
GRAFANA_ADMIN_PASSWORD
```

Use a Docker Hub access token rather than your Docker Hub password.

## 3. Terraform – create EKS

The Terraform configuration creates:

- VPC
- Two public subnets
- Internet gateway and route table
- EKS control plane
- Managed EC2 node group
- EKS IAM roles
- EBS CSI driver and OIDC IAM role

The default region is `ap-south-1`.

Amazon EKS currently lists Kubernetes 1.36, 1.35 and 1.34 in standard support; this project defaults to 1.36. Verify the version available in your selected AWS region before applying. urlAWS EKS Kubernetes version lifecyclehttps://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html

Run:

```bash
cd terraform
terraform init
copy terraform.tfvars.example terraform.tfvars
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

Then:

```bash
aws eks update-kubeconfig --region ap-south-1 --name medical-shop-eks
kubectl get nodes
```

### Important AWS cost/security note

The example uses public EKS API access and public subnets to keep the learning project straightforward. Restrict `cluster_public_access_cidrs` to your trusted network for a real deployment. EKS, EC2, NAT/load-balancer resources and EBS can incur AWS charges.

## 4. Kubernetes

Before manual deployment, create the secrets without committing real credentials:

```bash
kubectl -n medical-shop create secret generic mysql-secret --from-literal=MYSQL_ROOT_PASSWORD='"'"'CHANGE_ME'"'"'
kubectl -n medical-shop create secret generic medical-shop-secret \
  --from-literal=MYSQL_PASSWORD='"'"'CHANGE_ME'"'"' \
  --from-literal=SECRET_KEY='"'"'CHANGE_ME'"'"' \
  --from-literal=MAIL_USERNAME='"'"''"'"' \
  --from-literal=MAIL_PASSWORD='"'"''"'"' \
  --from-literal=MAIL_RECIPIENTS='"'"''"'"'
```

Then edit:

- `k8s/deployment.yml` image name
- `k8s/deployment.yml` image name
- `k8s/ingress.yml` hostname
- Grafana secret and hostname

Then:

```bash
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/configmap.yml
kubectl apply -f k8s/mysql-init-configmap.yml
kubectl apply -f k8s/mysql.yml
kubectl apply -f k8s/service.yml
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/ingress.yml
kubectl apply -f k8s/expiry-cronjob.yml
```

Install an NGINX Ingress Controller in the EKS cluster before using `ingressClassName: nginx`.

## 5. Monitoring

The original Flask scheduler was changed to be opt-in so multiple Gunicorn workers do not create duplicate scheduled jobs. Kubernetes runs the expiry-alert check once per day through `k8s/expiry-cronjob.yml`.

Prometheus discovers pods that have these annotations:

```yaml
prometheus.io/scrape: "true"
prometheus.io/path: "/metrics"
prometheus.io/port: "5000"
```

The Flask deployment already contains these annotations.

Apply monitoring manually:

```bash
kubectl apply -f monitering/prometheus.yml
kubectl apply -f monitering/prometheus-rbac.yml
kubectl apply -f monitering/prometheus-deployment.yml
kubectl apply -f monitering/prometheus-service.yml
kubectl apply -f monitering/grafana/configmap.yml
kubectl apply -f monitering/grafana/secret.yml
kubectl apply -f monitering/grafana/deployment.yml
kubectl apply -f monitering/grafana/service.yml
kubectl apply -f monitering/grafana/ingress.yml
```

## 6. Ansible

Ansible is used for an existing Linux operations/deployment host, not for replacing the EKS managed node group.

Edit `ansible/inventory.ini`, then:

```bash
cd ansible
ansible-playbook -i inventory.ini playbook.yml
```

The role installs/verifies Docker, Docker Compose plugin, kubectl, Helm and common administration packages on Debian/Ubuntu hosts.

## 7. Why `pom.xml` exists in a Python project

The application itself is Python, so Maven is not required to run Flask. You specifically requested a Maven build file, so `pom.xml` is included as a **packaging/validation wrapper**. The CI pipeline runs `mvn package` to produce a DevOps package under `target/devops-package`.

## 8. Default application login

The supplied database initialization logic creates the existing default account:

```text
username: admin
password: admin123
```

Change this before production use.

## 9. Troubleshooting

### MySQL connection refused

Check:

```bash
kubectl -n medical-shop get pods
kubectl -n medical-shop logs deployment/mysql
kubectl -n medical-shop get svc mysql
```

The Flask application uses `MYSQL_HOST=mysql`, not `localhost`, inside Kubernetes.

### ImagePullBackOff

Check the Docker Hub image name and whether the repository is public. If it is private, configure an `imagePullSecret` and reference it from the deployment.

### Ingress has no external address

Check that an NGINX Ingress Controller is installed:

```bash
kubectl get ingressclass
kubectl get pods -A | grep -i ingress
```

### PVC remains Pending

Check the EBS CSI driver:

```bash
kubectl -n kube-system get pods | grep ebs-csi
kubectl get storageclass
```

## Security reminders

- Never commit SMTP passwords, AWS keys, Docker Hub tokens or real Kubernetes secrets.
- Rotate the SMTP app password that appeared in the original source if it was ever exposed.
- Replace the default `admin/admin123` application account.
- Restrict EKS public API CIDRs.
- Use TLS on the Ingress in a production deployment.
