FROM python:alpine3.7
COPY . /app
WORKDIR /app
RUN pip3 install pipenv
RUN apk add zlib-dev jpeg-dev gcc musl-dev
RUN pipenv install --system --deploy --ignore-pipfile
ENTRYPOINT [ "python" ]
CMD [ "app.py" ]
