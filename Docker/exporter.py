#!/bin/python
from kubernetes import client, config
import kubernetes.client
import rados
import rbd
import json
import os
from prometheus_client import start_http_server, Gauge
import time
import threading


class DiffCounter:
    def __init__(self):
        self.count = 0
    def cb_offset(self, offset, length, exists):
        if exists:
            self.count += length


# Generate configuration from Service Account
configuration = kubernetes.client.Configuration()

base_creds_path = '/var/run/secrets/kubernetes.io/serviceaccount'
with open(os.path.join(base_creds_path, 'token')) as token_file:
    configuration.api_key['authorization'] = 'Bearer {}'.format(token_file.read())
configuration.ssl_ca_cert = os.path.join(base_creds_path, 'ca.crt')
# Load the "kubernetes" service items.
service_host = os.environ['KUBERNETES_SERVICE_HOST']
service_port = os.environ['KUBERNETES_SERVICE_PORT']
configuration.host = 'https://{}:{}'.format(service_host, service_port)
v1 = client.CoreV1Api(kubernetes.client.ApiClient(configuration))

# define the ceph cluster configuration based on the configmaps and secrets from the namespace
cluster = rados.Rados(conffile='/etc/ceph/ceph.conf')
cluster.connect()

if os.environ['DRIVER'] == 'csi':
    pools = cluster.list_pools()
    ioctxs = {}
    for pool in pools:
        ioctxs[pool] = cluster.open_ioctx(str(pool))

if os.environ['DRIVER'] == 'flex':
    ioctx = cluster.open_ioctx(str(os.environ['REPLICA_POOL']))

# configs can be set in configuration class directly or using helper utility
# config.load_kube_config("/home/rundeck/.kube/config-amm")

obj = rbd.RBD()

data = {}


def getData_csi(pv_dict):
    # get all the PVs with there size and used size
    # for pv in pvs:
    key = next(iter(pv_dict))
    image = rbd.Image(ioctxs[pv_dict[key]], key)
    max_size = image.size()
    counter = DiffCounter()
    image.diff_iterate(0, max_size, None, counter.cb_offset)
    current_size = counter.count
    data[key] = {
        "size": max_size,
        "used": current_size
    }
    image.close()
    # make relation between the PV and the PVC and the NameSpace


def getData_flex(pv_dict):
    # get all the PVs with there size and used size
    # for pv in pvs:

    image = rbd.Image(ioctx, pv)
    max_size = image.size()
    counter = DiffCounter()
    image.diff_iterate(0, max_size, None, counter.cb_offset)
    current_size = counter.count
    data[pv] = {
        "size": max_size,
        "used": current_size
    }
    image.close()
    # make relation between the PV and the PVC and the NameSpace


pv_size_all = Gauge("pv_size_all", "How much the size of the PV", ['pv', 'pvc', 'namespace'])
pv_size_used = Gauge("pv_size_used", "How much used size of the PV", ['pv', 'pvc', 'namespace'])


def f():
    for pv in data:
        if 'pvc_name' in data[pv].keys():
            if data[pv]['pvc_name'] is not None:
                pv_size_all.labels(pv, data[pv]['pvc_name'], data[pv]['namespace']).set(data[pv]['size'])
                pv_size_used.labels(pv, data[pv]['pvc_name'], data[pv]['namespace']).set(data[pv]['used'])


def remove_di(volume_handle):
    out = volume_handle.split('-')
    length = len(out)
    return "csi-vol-" + out[length - 5] + '-' + out[length - 4] + '-' + out[length - 3] + '-' + out[length - 2] + '-' \
           + out[length - 1]


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(int(os.environ['EXPORTER_PORT']))
    while True:
        time.sleep(5)
        data = {}
        threads = []
        pvs = []
        k8s_pvcs = v1.list_persistent_volume_claim_for_all_namespaces(watch=False)
        if os.environ['DRIVER'] == 'csi':
            k8s_pvs = v1.list_persistent_volume(watch=False)
            # list all PVs from generated RBD object based on the context object
            for key in ioctxs:
                for value in obj.list(ioctxs[key]):
                    pvs.append({value: key})
            for pv in pvs:
                t = threading.Thread(target=getData_csi, args=(pv,))
                threads.append(t)
                t.start()
        if os.environ['DRIVER'] == 'flex':
            pvs = obj.list(ioctx)
            for pv in pvs:
                t = threading.Thread(target=getData_flex, args=(pv,))
                threads.append(t)
                t.start()
        for x in threads:
            x.join()
        if os.environ['DRIVER'] == 'csi':
            for i in k8s_pvcs.items:
                if i.spec.volume_name is not None:
                    for j in k8s_pvs.items:
                        # json.dumps(str(x.spec.csi))
                        if 'csi' in json.dumps(str(j.spec)):
                            cond = remove_di(str(j.spec.csi.volume_handle))
                            if cond in data.keys():
                                data[cond]["namespace"] = i.metadata.namespace
                                data[cond]["pvc_name"] = i.metadata.name
        if os.environ['DRIVER'] == 'flex':
            for i in k8s_pvcs.items:
                if i.spec.volume_name is not None and i.spec.volume_name in data.keys():
                    data[i.spec.volume_name]["namespace"] = i.metadata.namespace
                    data[i.spec.volume_name]["pvc_name"] = i.metadata.name
        f()
