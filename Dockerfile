FROM python:3.6.8

MAINTAINER Health Data Analytics

RUN  apt-get update -y && \
     apt-get upgrade -y && \
     apt-get dist-upgrade -y && \
     apt-get -y autoremove && \
     apt-get clean
RUN apt-get install -y p7zip \
    p7zip-full \
    unace \
    zip \
    unzip \
    less \
    vim

EXPOSE 5000

ENV APP_HOME /api
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY requirements.txt $APP_HOME

RUN pip3 install -r requirements.txt

COPY . .

RUN chmod +x load_nlpql.sh wait-for-it-extra.sh

CMD ["gunicorn", "api", "--config", "config.py", "-b", "5000"]

