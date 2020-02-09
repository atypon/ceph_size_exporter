## Size_Exporter
This tool is designed to collect data from Ceph using the API of the monitoring nodes to:
* list the PV (volumes) using the RBD and IOCTX
* connect to the Kubernetes cluster using the API via SA
* map PVs and PVCs with NameSpaces
* construct Prometheus metrics
    * pv_size_all
    * pv_size_used
* expose the Metrics to be scrapable via Prometheus

---
### Build Docker image
Docker image is based on the Ceph original image
```bash
rook/ceph:master
```  
The new image add the new wrapper and exporter scripts into the container and fire up the wrapper.

To build the image: 
```bash
$ docker build -t registry.local/ceph/size-exporter:v0.5 .
$ docker tag registry.local/ceph/size-exporter:v0.5 registry.local/ceph/size-exporter:latest
```
---
### Usage
We deploy the tool using the following Helm command:
```bash
$ helm install --name promreporter --namespace rook-ceph .
```