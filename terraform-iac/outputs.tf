output "instance_public_ip" {
  description = "IP público da instância"
  value       = oci_core_instance.rag_agent.public_ip
}

output "ssh_command" {
  description = "Comando pronto para conectar via SSH"
  value       = "ssh ubuntu@${oci_core_instance.rag_agent.public_ip}"
}

output "app_url" {
  description = "URL para acessar a aplicação depois que o docker compose subir"
  value       = "http://${oci_core_instance.rag_agent.public_ip}:${var.app_port}"
}
