FROM python:3.12-bookworm

COPY entrypoint.py /entrypoint.py
COPY report_template /report_template
COPY requirements.txt /requirements.txt

RUN pip install -r /requirements.txt

ENTRYPOINT [ "/entrypoint.py" ]
