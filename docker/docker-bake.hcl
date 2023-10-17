# docker-bake.hcl for building QeApp images
group "default" {
  targets = ["awb"]
}

variable "ORGANIZATION" {
  default = "aiidalab"
}

target "awb" {
  tags = ["${ORGANIZATION}/aiidalab-widgets-base:newly-baked"]
  context = "."
  contexts = {
    src = ".."
  }
}
