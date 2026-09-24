variable "aws_region" {
  description = "AWS region for the EKS cluster."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Short project name used in AWS resource names."
  type        = string
  default     = "medical-shop"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "medical-shop-eks"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.36"
}

variable "vpc_cidr" {
  description = "VPC CIDR."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two public subnet CIDRs."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "cluster_public_access_cidrs" {
  description = "CIDRs allowed to reach the EKS Kubernetes API. Restrict this to your office/VPN/GitHub runner network where possible."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.micro"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "MedicalShop"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}
