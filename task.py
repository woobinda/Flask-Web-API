# -*- coding: utf-8 -*- 
from flask import Flask, render_template, session, redirect, url_for, flash, json
from flask_bootstrap import Bootstrap
from flask_wtf import Form
from wtforms import TextAreaField, SubmitField, IntegerField, SelectField, StringField
from wtforms.validators import Required, Regexp
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os
from flask_script import Shell, Manager
import hashlib

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =\
			'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = '2=ls-5(h2b-)e8*b%ng=+yma7pqjkrq_k=ujgz(4e4%mkr4#8%'

db = SQLAlchemy(app)
bootstrap = Bootstrap(app)
manager = Manager(app)

secret = 'eJSN0hh43LC0qDWvoYnOXfvfkOZ7yoBjq'
shop_id = 300969
currencys = dict(card_uah=980, card_rub=643)


class Order(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	amount = db.Column(db.Integer)
	currency = db.Column(db.String)
	description = db.Column(db.Text)
	created_date = db.Column(db.DateTime)

	def __init__(self, amount, currency, description, created_date):
		self.amount = amount
		self.currency = currency
		self.description = description
		self.created_date = created_date

	def __repr__(self):
		return '%s' % self.id


class PayForm(Form):
	amount = IntegerField('Amount', validators=[Required()])
	currency = SelectField('Currency', choices=[('card_uah', 'UAH'),('card_rub', 'RUB')], validators=[Required()])
	description = TextAreaField('Description', validators=[Required()])
	submit = SubmitField('Submit')


def _get_sign(request, keys_required, secret):
	keys_sorted = sorted(keys_required)
	string_to_sign = ":".join(str(request[k]).encode("utf8") for k in keys_sorted) + secret
	sign = hashlib.md5(string_to_sign).hexdigest()
	return sign


@app.route('/', methods=['GET', 'POST'])
def index():
	order = Order.query.all()
	form = PayForm()

	if form.validate_on_submit():
		result = dict(amount=form.amount.data, currency=form.currency.data, description=form.description.data)
		created_date = datetime.now()
		order = Order(form.amount.data, form.currency.data, form.description.data, created_date)
		db.session.add(order)
		db.session.commit()
		if form.currency.data == 'card_rub':
			request = dict(shop_id=shop_id, amount=form.amount.data, shop_invoice_id=order.id, currency=currencys[form.currency.data])
			keys_required = ("shop_id", "amount", "currency", "shop_invoice_id")
			sign = _get_sign(request, keys_required, secret)
			session['sign']=sign
			url = 'https://tip.pay-trio.com/ru/' + '?amount=' + str(form.amount.data) + '&currency=' + str(currencys[form.currency.data]) + \
			'&shop_id=' + str(shop_id) + '&shop_invoice_id=' + str(order.id) + '&sign=' + str(sign)
			# return redirect(url)

		if form.currency.data == 'card_uah':
			request = dict(amount=form.amount.data, currency=currencys[form.currency.data], payway=form.currency.data, shop_id=shop_id, shop_invoice_id=order.id)
			keys_required = ("amount", "currency", "payway", "shop_id", "shop_invoice_id")
			sign = _get_sign(request, keys_required, secret)
			session['sign']=sign
			request['sign'] = sign
			request['description'] = form.description.data
			request_to_api = json.dumps(request, sort_keys=True, indent=4)
			session['request_to_api'] = request_to_api
			print(request_to_api)

		return redirect(url_for('index'))
	return render_template('payform.html', form=form, order=order, sign=session.get('sign'), request_to_api=session.get('request_to_api'))


@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404


if __name__ == '__main__':
	app.run(debug=True)
