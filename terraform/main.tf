terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.3"
    }
  }
}

# ============================================================
# PROVIDERS
# ============================================================

provider "aws" {
  region = var.aws_region
}

# Helm connects directly to the EKS API.
# AWS CLI is used to generate the short-lived EKS authentication token.
provider "helm" {
  kubernetes = {
    host                   = aws_eks_cluster.main.endpoint
    cluster_ca_certificate = base64decode(
      aws_eks_cluster.main.certificate_authority[0].data
    )

    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"

      command = "aws"

      args = [
        "eks",
        "get-token",
        "--cluster-name",
        aws_eks_cluster.main.name,
        "--region",
        var.aws_region
      ]
    }
  }
}

# ============================================================
# DATA SOURCES
# ============================================================

data "aws_availability_zones" "available" {
  state = "available"
}

# AWS identity running Terraform.
# This identity will receive EKS administrator access.
data "aws_caller_identity" "current" {}

# ============================================================
# IAM POLICY DOCUMENTS
# ============================================================

data "aws_iam_policy_document" "eks_assume_role" {
  statement {
    effect  = "Allow"

    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type = "Service"

      identifiers = [
        "eks.amazonaws.com"
      ]
    }
  }
}

data "aws_iam_policy_document" "node_assume_role" {
  statement {
    effect = "Allow"

    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type = "Service"

      identifiers = [
        "ec2.amazonaws.com"
      ]
    }
  }
}

# ============================================================
# VPC
# ============================================================

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-vpc"
    }
  )
}

# ============================================================
# INTERNET GATEWAY
# ============================================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-igw"
    }
  )
}

# ============================================================
# PUBLIC SUBNETS
# ============================================================

resource "aws_subnet" "public" {
  count = 2

  vpc_id = aws_vpc.main.id

  cidr_block = var.public_subnet_cidrs[count.index]

  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-public-${count.index + 1}"

      "kubernetes.io/role/elb" = "1"

      "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    }
  )
}

# ============================================================
# PUBLIC ROUTE TABLE
# ============================================================

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-public-rt"
    }
  )
}

resource "aws_route" "internet" {
  route_table_id = aws_route_table.public.id

  destination_cidr_block = "0.0.0.0/0"

  gateway_id = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id = aws_subnet.public[count.index].id

  route_table_id = aws_route_table.public.id
}

# ============================================================
# EKS CLUSTER IAM ROLE
# ============================================================

resource "aws_iam_role" "eks_cluster" {
  name = "${var.project_name}-eks-cluster-role"

  assume_role_policy = data.aws_iam_policy_document.eks_assume_role.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role = aws_iam_role.eks_cluster.name

  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# ============================================================
# EKS CLUSTER
# ============================================================

resource "aws_eks_cluster" "main" {
  name = var.cluster_name

  role_arn = aws_iam_role.eks_cluster.arn

  version = var.kubernetes_version

  vpc_config {
    subnet_ids = aws_subnet.public[*].id

    endpoint_private_access = false

    endpoint_public_access = true

    public_access_cidrs = var.cluster_public_access_cidrs
  }

  # EKS API authentication.
  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy
  ]
}

# ============================================================
# EKS ACCESS ENTRY
# ============================================================
#
# Gives the AWS identity running Terraform access to EKS.
#
# Fixes:
# "the server has asked for the client to provide credentials"
#

resource "aws_eks_access_entry" "terraform_admin" {
  cluster_name = aws_eks_cluster.main.name

  principal_arn = data.aws_caller_identity.current.arn

  type = "STANDARD"

  depends_on = [
    aws_eks_cluster.main
  ]
}

# ============================================================
# EKS ADMIN ACCESS POLICY
# ============================================================

resource "aws_eks_access_policy_association" "terraform_admin" {
  cluster_name = aws_eks_cluster.main.name

  principal_arn = data.aws_caller_identity.current.arn

  policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [
    aws_eks_access_entry.terraform_admin
  ]
}

# ============================================================
# EKS NODE IAM ROLE
# ============================================================

resource "aws_iam_role" "nodes" {
  name = "${var.project_name}-eks-node-role"

  assume_role_policy = data.aws_iam_policy_document.node_assume_role.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "worker" {
  role = aws_iam_role.nodes.name

  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "cni" {
  role = aws_iam_role.nodes.name

  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr" {
  role = aws_iam_role.nodes.name

  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# ============================================================
# EKS NODE GROUP
# ============================================================

resource "aws_eks_node_group" "main" {
  cluster_name = aws_eks_cluster.main.name

  node_group_name = "${var.project_name}-nodes"

  node_role_arn = aws_iam_role.nodes.arn

  subnet_ids = aws_subnet.public[*].id

  # Controlled through variables.tf / terraform.tfvars.
  #
  # Recommended current value:
  # node_instance_types = ["t3.small"]
  #
  instance_types = var.node_instance_types

  ami_type = "AL2023_x86_64_STANDARD"

  capacity_type = "ON_DEMAND"

  scaling_config {
    desired_size = var.node_desired_size

    min_size = var.node_min_size

    max_size = var.node_max_size
  }

  update_config {
    max_unavailable = 3
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.worker,
    aws_iam_role_policy_attachment.cni,
    aws_iam_role_policy_attachment.ecr
  ]
}

# ============================================================
# EKS OIDC PROVIDER
# ============================================================

data "tls_certificate" "eks_oidc" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    data.tls_certificate.eks_oidc.certificates[0].sha1_fingerprint
  ]

  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

# ============================================================
# EBS CSI DRIVER ASSUME ROLE
# ============================================================

data "aws_iam_policy_document" "ebs_csi_assume" {
  statement {
    effect = "Allow"

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    principals {
      type = "Federated"

      identifiers = [
        aws_iam_openid_connect_provider.eks.arn
      ]
    }

    condition {
      test = "StringEquals"

      variable = "${replace(
        aws_iam_openid_connect_provider.eks.url,
        "https://",
        ""
      )}:aud"

      values = [
        "sts.amazonaws.com"
      ]
    }

    condition {
      test = "StringEquals"

      variable = "${replace(
        aws_iam_openid_connect_provider.eks.url,
        "https://",
        ""
      )}:sub"

      values = [
        "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      ]
    }
  }
}

# ============================================================
# EBS CSI IAM ROLE
# ============================================================

resource "aws_iam_role" "ebs_csi" {
  name = "${var.project_name}-ebs-csi-role"

  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role = aws_iam_role.ebs_csi.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# ============================================================
# EBS CSI ADDON
# ============================================================

resource "aws_eks_addon" "ebs_csi" {
  cluster_name = aws_eks_cluster.main.name

  addon_name = "aws-ebs-csi-driver"

  addon_version = "v1.66.0-eksbuild.1"

  service_account_role_arn = aws_iam_role.ebs_csi.arn

  resolve_conflicts_on_create = "OVERWRITE"

  resolve_conflicts_on_update = "PRESERVE"

  depends_on = [
    aws_eks_node_group.main,
    aws_iam_role_policy_attachment.ebs_csi
  ]
}

# ============================================================
# NGINX INGRESS CONTROLLER
# ============================================================
#
# This replaces the manual command:
#
# helm install ingress-nginx ingress-nginx/ingress-nginx
# --namespace ingress-nginx
# --create-namespace
# --set controller.service.type=LoadBalancer
#
# Terraform will now install and manage it.
#

resource "helm_release" "ingress_nginx" {
  name = "ingress-nginx"

  repository = "https://kubernetes.github.io/ingress-nginx"

  chart = "ingress-nginx"

  namespace = "ingress-nginx"

  create_namespace = true

  wait = true

  timeout = 900

  set = [
    {
      name  = "controller.service.type"
      value = "LoadBalancer"
    }
  ]

  depends_on = [
    aws_eks_node_group.main,
    aws_eks_access_policy_association.terraform_admin
  ]
}