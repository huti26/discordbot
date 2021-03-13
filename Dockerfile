FROM python:3.8-slim
WORKDIR /discordapp

# Need build-essential for building wheels
RUN apt-get update
RUN apt-get install build-essential -y --no-install-recommends

# First copy just the requirements and install them
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

#
COPY entrypoint.sh entrypoint.sh

RUN ["chmod", "+x", "entrypoint.sh"]

# Only part that changes, do this last for maximum caching
COPY ./Bot/ ./Bot/

CMD ["./entrypoint.sh"]
