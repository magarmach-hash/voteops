# 🗳️ Voting App — Complete Setup Guide
## EC2 + Minikube + ArgoCD + Helm + Prometheus + Grafana

---

## 1. AWS EC2 Setup

### Launch Instance
- AMI: Ubuntu 22.04 LTS
- Instance type: t3.medium (2 vCPU, 4GB RAM minimum for minikube)
- Storage: 20GB root volume
- Security Group — open these ports:
  - 22   (SSH)
  - 80   (HTTP)
  - 443  (HTTPS)
  - 8080 (ArgoCD UI)
  - 9090 (Prometheus)
  - 3000 (Grafana)
  - 30080 (NodePort for app)
  - 30000–32767 (NodePort range)

### Connect & Prep the EC2
```bash
ssh -i yourkey.pem ubuntu@<EC2_PUBLIC_IP>

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
sudo apt-get install -y docker.io
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker ubuntu
newgrp docker    # reload group without logout
```

---

## 2. Install kubectl
```bash
curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/
kubectl version --client
```

---

## 3. Install Minikube
```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start with docker driver (enough for t3.medium)
minikube start --driver=docker --cpus=2 --memory=3500mb

# Verify
minikube status
kubectl get nodes
```

---

## 4. Install Helm
```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

---

## 5. Install ArgoCD

```bash
# Create namespace and install
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods to be ready
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=120s

# Patch ArgoCD server to NodePort so you can access the UI
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort"}}'

# Get the NodePort
kubectl get svc argocd-server -n argocd

# Get initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath="{.data.password}" | base64 -d && echo

# Install ArgoCD CLI (optional but useful)
curl -sSL -o argocd-linux-amd64 \
  https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd

# Get minikube IP to access ArgoCD UI
minikube ip
# Access: https://<minikube-ip>:<nodeport>
# Or use port-forward:
kubectl port-forward svc/argocd-server -n argocd 8080:443 --address=0.0.0.0 &
# Access: https://<EC2_PUBLIC_IP>:8080
# Login: admin / <password from above>
```

---

## 6. Docker Hub Setup
1. Create account at hub.docker.com
2. Create a repo named `voting-app`
3. In GitHub repo → Settings → Secrets → Actions, add:
   - `DOCKERHUB_USERNAME` — your Docker Hub username
   - `DOCKERHUB_TOKEN`    — Docker Hub access token (Account Settings → Security)
   - `GH_PAT`             — GitHub Personal Access Token with `repo` scope

---

## 7. Clone Repo & Apply ArgoCD App

```bash
# On EC2
git clone https://github.com/YOURUSER/voting-app.git
cd voting-app

# Edit the ArgoCD app manifest with your repo URL first!
nano k8s/argocd-app.yaml   # set repoURL to your GitHub URL

# Apply it — ArgoCD will now watch your Helm chart
kubectl apply -f k8s/argocd-app.yaml

# Check sync status
kubectl get application -n argocd
# Or use: argocd app list
```

Once applied, every time CI pushes a new image tag to `values.yaml`,
ArgoCD will automatically detect the git change and redeploy.

---

## 8. Access the Voting App

```bash
# Get NodePort service URL
minikube service voting-app-service -n voting --url

# Or port-forward to access from your machine
kubectl port-forward svc/voting-app-service -n voting 5000:80 --address=0.0.0.0 &
# Access: http://<EC2_PUBLIC_IP>:5000
```

---

## 9. Install Prometheus + Grafana (Monitoring)

```bash
# Add the kube-prometheus-stack helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install the full stack (Prometheus + Grafana + node-exporter + alertmanager)
kubectl create namespace monitoring

helm install kube-prom-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.service.type=NodePort \
  --set grafana.service.nodePort=30300 \
  --set prometheus.service.type=NodePort \
  --set prometheus.service.nodePort=30090

# Wait for pods
kubectl get pods -n monitoring -w

# Get Grafana admin password
kubectl get secret --namespace monitoring kube-prom-stack-grafana \
  -o jsonpath="{.data.admin-password}" | base64 -d && echo
# Default user: admin

# Port-forward Grafana (alternative to NodePort)
kubectl port-forward svc/kube-prom-stack-grafana -n monitoring 3000:80 --address=0.0.0.0 &
# Access: http://<EC2_PUBLIC_IP>:3000

# Port-forward Prometheus
kubectl port-forward svc/kube-prom-stack-kube-prom-prometheus -n monitoring 9090:9090 --address=0.0.0.0 &
# Access: http://<EC2_PUBLIC_IP>:9090
```

### Grafana Dashboards to Import
- **ID 315** — Kubernetes cluster monitoring (by Instrumenta)
- **ID 6417** — Kubernetes pods and containers
- **ID 1860** — Node Exporter Full

To import: Grafana → Dashboards → Import → enter the ID → Load

---

## 10. Local Dev (docker-compose)

```bash
# On your laptop — just needs Docker
cd voting-app
docker-compose up --build

# App at: http://localhost:5000
```

---

## 11. CI/CD Flow Summary

```
You push code to main
       │
       ▼
GitHub Actions: git diff detects app/ changed?
       │ yes
       ▼
Build Docker image → tag with short SHA (abc1234)
Push to Docker Hub: youruser/voting-app:abc1234
       │
       ▼
Commit updated helm/voting-app/values.yaml
  (tag: "latest" → tag: "abc1234")
       │
       ▼
ArgoCD detects git change in values.yaml
       │
       ▼
ArgoCD syncs Helm chart → new pods roll out
```

---

## 12. Useful Commands Cheatsheet

```bash
# Minikube
minikube status
minikube dashboard          # opens k8s dashboard in browser (tunnel)
minikube stop / start

# App
kubectl get all -n voting
kubectl logs -f deploy/voting-app -n voting
kubectl describe pod -l app=voting-app -n voting

# ArgoCD
argocd app list
argocd app sync voting-app
argocd app get voting-app

# Helm
helm list -A
helm status voting-app -n voting
helm history voting-app -n voting
# Rollback if something breaks:
helm rollback voting-app 1 -n voting

# Monitoring
kubectl get pods -n monitoring
kubectl top nodes
kubectl top pods -n voting
```
