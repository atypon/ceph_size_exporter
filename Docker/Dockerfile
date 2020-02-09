FROM rook/ceph:master

RUN yum install -y python-pip  && \
    pip install --upgrade pip  && \
    pip install prometheus_client

COPY  exporter.py wrapper.sh /usr/local/bin/
RUN chmod 777 /usr/local/bin/exporter.py /usr/local/bin/wrapper.sh