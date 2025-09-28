FROM python:3-alpine

WORKDIR /app

COPY pyproject.toml setup.py /app/

RUN pip3 install .[apiserver]

COPY . /app

EXPOSE 8080

ENTRYPOINT ["python3"]

CMD ["-m", "gui_agents.api"]
