output "cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "EKS cluster name."
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "EKS Kubernetes API endpoint."
}

output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID."
}

output "kubectl_config_command" {
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.main.name}"
  description = "Command to configure kubectl."
}
