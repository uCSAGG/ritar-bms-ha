FROM python:3.9-alpine

ENV HASSIO_DATA_PATH=/data

RUN apk add --no-cache python3

RUN mkdir /web_ui
RUN mkdir /web_ui/api
RUN touch /web_ui/api/ritar-bat-1.xml | touch /web_ui/api/ritar-bat-2.xml | touch /web_ui/api/ritar-bat-3.xml | touch /web_ui/api/ritar-bat-4.xml

WORKDIR /web_ui

COPY ritar-bms.py run.sh /
RUN pip3 install pyyaml
RUN chmod a+x /run.sh

CMD [ "sh", "/run.sh" ]
