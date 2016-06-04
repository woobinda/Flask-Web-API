# -*- coding: utf-8 -*- 
from flask import Flask, render_template, session, redirect, url_for, json
from flask_bootstrap import Bootstrap
from flask_wtf import Form
from wtforms import TextAreaField, SubmitField, IntegerField, SelectField, StringField
from wtforms.validators import Required, Regexp
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_script import Shell, Manager
import os
import hashlib
import requests
import logging


app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = \
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = os.urandom(24)

db = SQLAlchemy(app)
bootstrap = Bootstrap(app)
manager = Manager(app)

secret = 'eJSN0hh43LC0qDWvoYnOXfvfkOZ7yoBjq'
shop_id = 300969
currencys = dict(w1_uah=980, card_rub=643)


class PayForm(Form):
    amount = IntegerField('Amount', validators=[Required()])
    currency = SelectField('Currency', choices=[('w1_uah', 'UAH'), ('card_rub', 'RUB')], validators=[Required()])
    description = TextAreaField('Description', validators=[Required()])
    submit = SubmitField('Submit')


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


def _get_sign(request, keys_required, secret):
    keys_sorted = sorted(keys_required)
    string_to_sign = ":".join(str(request[k]).encode("utf8") for k in keys_sorted) + secret
    sign = hashlib.md5(string_to_sign).hexdigest()
    return sign


@app.route('/', methods=['GET', 'POST'])
def index():
    form = PayForm()
    logging.info('---Start---')

    if form.validate_on_submit():
        created_date = datetime.now()
        order = Order(form.amount.data, form.currency.data, form.description.data, created_date)
        db.session.add(order)
        db.session.commit()
        app.logger.info('Create a order (id %s)' % order.id)

        if form.currency.data == 'card_rub':
            logging.info('Starting redirect')
            request = dict(shop_id=shop_id, amount=form.amount.data, shop_invoice_id=order.id,
                           currency=currencys[form.currency.data])
            app.logger.debug('Choicen payway is ( %s)' % form.currency.data)
            keys_required = ("shop_id", "amount", "currency", "shop_invoice_id")
            sign = _get_sign(request, keys_required, secret)
            app.logger.info('Generate a HTML form')
            return render_template('payform_rub.html', amount=str(form.amount.data),
                                   currency=str(currencys[form.currency.data]), shop_id=str(shop_id),
                                   shop_invoice_id=str(order.id), sign=str(sign),
                                   description=str(form.description.data),
                                   failed_url="https://tip.pay-trio.com/failed/",
                                   success_url="https://tip.pay-trio.com/success/")

        if form.currency.data == 'w1_uah':
            request = dict(amount=form.amount.data, currency=currencys[form.currency.data],
                           payway=form.currency.data, shop_id=shop_id, shop_invoice_id=order.id)
            app.logger.info('Currency is ( %s)' % form.currency.data)
            keys_required = ("amount", "currency", "payway", "shop_id", "shop_invoice_id")
            sign = _get_sign(request, keys_required, secret)
            request['sign'] = sign
            request['description'] = form.description.data
            url = "https://central.pay-trio.com/invoice"
            headers = {'Content-type': 'application/json'}
            request_to_api = requests.post(url, data=json.dumps(request), headers=headers)
            response_from_api = json.loads(request_to_api.text)
            app.logger.debug('Response_from_api result is ( %s)' % response_from_api['result'])
            if response_from_api['result'] == 'ok':
                data = response_from_api['data']['data']
                app.logger.info('Generate a HTML form')
                return render_template('payform_uah.html', WMI_CURRENCY_ID=str(data['WMI_CURRENCY_ID']),
                                       WMI_FAIL_URL=str(data['WMI_FAIL_URL']),
                                       WMI_MERCHANT_ID=str(data['WMI_MERCHANT_ID']),
                                       WMI_PAYMENT_AMOUNT=str(data['WMI_PAYMENT_AMOUNT']),
                                       WMI_PAYMENT_NO=str(data['WMI_PAYMENT_NO']),
                                       WMI_PTENABLED=str(data['WMI_PTENABLED']),
                                       WMI_SIGNATURE=str(data['WMI_SIGNATURE']),
                                       WMI_SUCCESS_URL=str(data['WMI_SUCCESS_URL']))
    else:
        app.logger.debug('Validation Form Error')
    return render_template('payform_index.html', form=form)


@app.errorhandler(404)
def page_not_found(e):
    app.logger.debug('404 Not Found')
    return render_template('404.html'), 404


if __name__ == '__main__':
    logging.basicConfig(filename='app.log', filemode='w', level=logging.DEBUG)
    logging.debug('This message should go to the log file')
    app.run(debug=True)
