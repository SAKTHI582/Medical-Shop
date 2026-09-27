# ============================================================
# AWS REGION
# ============================================================

variable "aws_region" {
  description = "AWS region for the EKS cluster."
  type        = string
  default     = "ap-south-1"
}


# ============================================================
# PROJECT
# ============================================================

variable "project_name" {
  description = "Short project name used in AWS resource names."
  type        = string
  default     = "medical-shop"
}


# ============================================================
# EKS CLUSTER
# ============================================================

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "medical-shop-eks"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS cluster."
  type        = string
  default     = "1.36"
}


# ============================================================
# VPC
# ============================================================

variable "vpc_cidr" {
  description = "CIDR block for the Medical Shop VPC."
  type        = string
  default     = "10.0.0.0/16"
}


# ============================================================
# PUBLIC SUBNETS
# ============================================================

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets."
  type        = list(string)

  default = [
    "10.0.1.0/24",
    "10.0.2.0/24"
  ]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required."
  }
}


# ============================================================
# EKS API PUBLIC ACCESS
# ============================================================

variable "cluster_public_access_cidrs" {
  description = "CIDRs allowed to access the EKS Kubernetes API."

  type = list(string)

  # WARNING:
  # 0.0.0.0/0 allows the Kubernetes API to be reached
  # from anywhere on the Internet.
  #
  # For learning/testing this can be used temporarily.
  # For production, replace it with your public IP/32.
  default = [
    "0.0.0.0/0"
  ]
}


# ============================================================
# EKS NODE INSTANCE TYPES
# ============================================================

variable "node_instance_types" {
  description = "EC2 instance types used by the EKS managed node group."

  type = list(string)

  # t3.small is suitable for this project and provides
  # more capacity than t3.micro for Kubernetes system pods.
  default = [
    "m7i-flex.large"
  ]
}


# ============================================================
# EKS NODE GROUP SCALING
# ============================================================

variable "node_desired_size" {
  description = "Desired number of EKS worker nodes."
  type        = number
  default     = 2

  validation {
    condition     = var.node_desired_size >= 1
    error_message = "The desired node count must be at least 1."
  }
}

variable "node_min_size" {
  description = "Minimum number of EKS worker nodes."
  type        = number
  default     = 2

  validation {
    condition     = var.node_min_size >= 1
    error_message = "The minimum node count must be at least 1."
  }
}

variable "node_max_size" {
  description = "Maximum number of EKS worker nodes."
  type        = number
  default     = 3

  validation {
    condition     = var.node_max_size >= var.node_min_size
    error_message = "The maximum node count must be greater than or equal to the minimum node count."
  }
}


# ============================================================
# RESOURCE TAGS
# ============================================================

variable "tags" {
  description = "Common tags applied to AWS resources."
  type        = map(string)

  default = {
    Project     = "MedicalShop"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}
