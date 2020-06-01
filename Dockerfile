FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt functional_tests.py test_main.py main.py templates.py app/

RUN pip install -r app/requirements.txt

CMD ["python", "functional_tests.py"]

CMD ["python", "-m", "unittest", "discover"]

ENTRYPOINT ["main.py"]