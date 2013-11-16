""" Criticizer backend using Flask. """

import json

import yaml
from flask import Flask, request, jsonify
import sqlalchemy
from dateutil import parser

from rtapi import RTAPI
from model import Base, Movie, Critic, Review

app = Flask(__name__)

engine = sqlalchemy.create_engine('sqlite:////home/travis/movie.db')
Session = sqlalchemy.orm.sessionmaker(bind=engine)
session = Session()

Base.metadata.create_all(engine)

config = yaml.load(open('criticizer/config.yml', 'r').read())
rt = RTAPI(config.get('api_key'))

@app.route('/movies', methods=['GET'])
def movies():
    """ Return JSON list of the given movies from the search API. """
    data = json.loads(request.args.get('data')).get('movies')
    return jsonify(movies=[rt.search(movie) for movie in data])

@app.route('/reviews', methods=['GET'])
def reviews():
    """ Return JSON list of the reviews of the given movies. """
    data = json.loads(request.args.get('data')).get('movies')

    # TODO: we'll need our own search, solr or something
    # TODO: adding stuff to backend should be async

    for movie in data:
        if session.query(Movie).filter_by(title=movie).count() == 0:
            add_movie_to_backend(movie)

    # all movies exist in the backend at this point
    movies = [session.query(Movie).filter_by(title=movie).first()
              for movie in data]
    reviews = [[review.to_json() for review in movie.reviews] for movie in movies]
    return jsonify(reviews=reviews)

def add_movie_to_backend(title):

    result = rt.reviews(title)
    if not result:
        raise ValueError('no movie found for {}'.format(title))

    movie = Movie(result['id'], result['title'])

    for review in result.get('reviews', []):
        dt = parser.parse(review['date']) if review.get('date', None) else None
        review_obj = Review(review['freshness'] == 'fresh',
                            review.get('original_score', None),
                            review.get('quote', None),
                            review.get('url', None),
                            dt)

        critic_query = session.query(Critic).filter_by(name=review['critic'])
        if review.get('publication', None):
            critic_query = critic_query.filter_by(publication=review['publication'])

        critic = critic_query.first()
        if not critic:
            critic = Critic(review['critic'], review.get('publication', None))

        review_obj.movie = movie
        review_obj.critic = critic

    session.add(review_obj)
    session.commit()

def init_app():
    app.debug = True
    app.run(host='127.0.0.1', port=5000)

if __name__ == '__main__':
    init_app()
