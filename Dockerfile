FROM mongo:4.2
FROM python:3

# set a directory for the app
WORKDIR /

# copy all the files to the container
COPY . .

#install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask-PyMongo

# Flask app run on port 5000python
EXPOSE 5000

ENTRYPOINT ["python"]
CMD ["app.py"]