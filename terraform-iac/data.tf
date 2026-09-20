# Descobre os availability domains disponíveis no compartimento/região
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# Descobre automaticamente a imagem Ubuntu mais recente compatível com o
# shape escolhido — evita hardcodar um OCID de imagem que muda por região.
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}
