# Use the official Python image from Docker Hub
FROM python:3.11.15

# Update apt-get
RUN apt-get update

# Install dependencies
COPY requirements.txt .

RUN pip3 install -r requirements.txt

ADD app /app

WORKDIR /app

CMD tail -f /dev/null
