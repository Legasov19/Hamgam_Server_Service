from flask import Blueprint, render_template
from models.database import process_sepidar

sepidar_bp = Blueprint('sepidar', __name__)

@sepidar_bp.route('/')
def sepidar_page():
    result = process_sepidar()
    return render_template('sepidar.html', result=result)
