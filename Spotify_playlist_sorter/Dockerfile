FROM python:3.8

COPY requirments.txt . 

RUN pip install -r requirments.txt

COPY . .

EXPOSE  1234

CMD ["flask", "run","--host=0.0.0.0", "--port=1234"]