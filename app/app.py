# -*- coding: utf-8 -*-
import hashlib
import logging
import os
import requests

from datetime import datetime
from flask import Flask, render_template, json
from flask_bootstrap import Bootstrap
from flask_script import Manager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, IntegerField, SelectField
from wtforms.validators import Required


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

# incoming constants
secret = 'eJSN0hh43LC0qDWvoYnOXfvfkOZ7yoBjq'
shop_id = 300969
currencies = dict(w1_uah=980, card_rub=643)


class PayForm(FlaskForm):
    """
    Customer form

      amount        - payment amount
      currency      - payment currenct
      description   - payment description

    """
    amount = IntegerField(u'Сумма оплаты', validators=[Required()])
    currency = SelectField(u'Валюта оплаты', choices=[(
        'w1_uah', 'UAH'), ('card_rub', 'RUB')], validators=[Required()])
    description = TextAreaField(u'Описание товара', validators=[Required()])
    submit = SubmitField(u'Оплатить')


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
    """
    Algorithm to produce a unique digital signature for all transactions
    """
    keys_sorted = sorted(keys_required)
    string_to_sign = ":".join(str(request[k]).encode(
        "utf8") for k in keys_sorted) + secret
    sign = hashlib.md5(string_to_sign).hexdigest()
    return sign


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Feature provides a record of the data entered into the form,
    and redirect the user to the relevant payment system
    """
    form = PayForm()
    if form.validate_on_submit():
        created_date = datetime.now()
        order = Order(form.amount.data, form.currency.data,
                      form.description.data, created_date)
        db.session.add(order)
        db.session.commit()
        app.logger.info('Create a order (id = %s)' % order.id)

        if form.currency.data == 'card_rub':
            app.logger.info("Payway is '%s'" % form.currency.data)
            request = dict(shop_id=shop_id, amount=form.amount.data, shop_invoice_id=order.id,
                           currency=currencies[form.currency.data])
            app.logger.info("Request is: %s" % request)
            keys_required = ("shop_id", "amount",
                             "currency", "shop_invoice_id")
            sign = _get_sign(request, keys_required, secret)
            app.logger.info('Generate a HTML form for redirect')
            return render_template('payform_rub.html',
                                   amount=str(form.amount.data),
                                   currency=str(
                                       currencies[form.currency.data]),
                                   shop_id=str(shop_id),
                                   shop_invoice_id=str(order.id),
                                   sign=str(sign),
                                   description=(form.description.data).encode(
                                       'ascii', 'ignore'),
                                   failed_url="https://tip.pay-trio.com/failed/",
                                   success_url="https://tip.pay-trio.com/success/")

        if form.currency.data == 'w1_uah':
            app.logger.info("Payway is '%s'" % form.currency.data)
            request = dict(amount=form.amount.data,
                           currency=currencies[form.currency.data],
                           payway=form.currency.data,
                           shop_id=shop_id,
                           shop_invoice_id=order.id)
            keys_required = ("amount", "currency", "payway",
                             "shop_id", "shop_invoice_id")
            sign = _get_sign(request, keys_required, secret)
            request["sign"] = sign
            request["description"] = form.description.data
            url = "https://central.pay-trio.com/invoice"
            app.logger.info("Request to API is: %s" % request)
            request_to_api = requests.post(url, data=json.dumps(request), headers={
                                           'Content-type': 'application/json'})
            response_from_api = json.loads(request_to_api.text)
            app.logger.info("Response from API is: %s" % response_from_api)

            if response_from_api['result'] == 'ok':
                data = response_from_api['data']['data']
                app.logger.info('Generate a HTML form for redirect')
                return render_template('payform_uah.html',
                                       WMI_CURRENCY_ID=str(
                                           data["WMI_CURRENCY_ID"]),
                                       WMI_FAIL_URL=str(data["WMI_FAIL_URL"]),
                                       WMI_MERCHANT_ID=str(
                                           data["WMI_MERCHANT_ID"]),
                                       WMI_PAYMENT_AMOUNT=str(
                                           data["WMI_PAYMENT_AMOUNT"]),
                                       WMI_PAYMENT_NO=str(
                                           data["WMI_PAYMENT_NO"]),
                                       WMI_PTENABLED=str(
                                           data["WMI_PTENABLED"]),
                                       WMI_SIGNATURE=str(
                                           data["WMI_SIGNATURE"]),
                                       WMI_SUCCESS_URL=str(data["WMI_SUCCESS_URL"]))
            else:
                app.logger.error(
                    "API Response result is (%s)" % response_from_api['result'])
                return render_template('500.html')
    return render_template('payform_index.html', form=form)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error('Error 500, Internal Server Error')
    return render_template('500.html'), 500


if __name__ == '__main__':
    logging.basicConfig(filename='app.log', filemode='w',
                        level=logging.INFO, threaded=True)
    app.run(host='localhost')
