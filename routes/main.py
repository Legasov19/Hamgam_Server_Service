from flask import Blueprint, render_template, request, redirect, url_for
from models.database import DATABASE

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        item = request.form.get('item')
        if item:
            DATABASE.append(item)
            if item == 'هلو':
                return redirect(url_for('Holoo.Holoo_page'))
            elif item == 'سپیدار':
                return redirect(url_for('sepidar.sepidar_page'))
    return render_template('index.html', database=DATABASE)
