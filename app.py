from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory, g, send_file
from pymongo import MongoClient
import bcrypt
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import pytz
from sib_api_v3_sdk import Configuration, ApiClient
from sib_api_v3_sdk.api.transactional_emails_api import TransactionalEmailsApi
from sib_api_v3_sdk.models import SendSmtpEmail, SendSmtpEmailSender, SendSmtpEmailTo
import pandas as pd
import io

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
app.secret_key = "rahasia"

client = MongoClient("mongodb://test:test@ac-owhiyhy-shard-00-00.6znvghk.mongodb.net:27017,ac-owhiyhy-shard-00-01.6znvghk.mongodb.net:27017,ac-owhiyhy-shard-00-02.6znvghk.mongodb.net:27017/?ssl=true&replicaSet=atlas-10141m-shard-0&authSource=admin&retryWrites=true&w=majority")
MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")
db = client["Cluster0"]
users_collection = db["user"]
equipment_collection = db["equipment"]
borrowed_equipment_collection = db["borrowed_equipment"]
projects_collection = db['project']
messages_collection = db["messages"]
notifications_collection = db['notification']
tokens_collection = db['tokens']
borrowed_requests_collection = db['borrowed_requests']
sample_collection = db['sample']
statistik_collection = db['statistik']

# Konfigurasi API client dengan API key Anda
configuration = Configuration()
configuration.api_key['api-key'] = os.getenv('SENDINBLUE_API_KEY')
api_client = ApiClient(configuration)
api_instance = TransactionalEmailsApi(api_client)
# Configure the upload folder
UPLOAD_FOLDER = 'static/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.context_processor
def inject_user_data():
    user_data = None
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
    return dict(user_data=user_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        user_data = users_collection.find_one({'email': email})
        if user_data and bcrypt.checkpw(password, user_data['password']):
            session['user_id'] = str(user_data['_id'])
            session['user'] = {
                '_id': str(user_data['_id']),
                'name': user_data['name'],
                'email': user_data['email'],
                'role': user_data['role']
            }
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid email or password')

    return render_template('login.html')

@app.route('/')
def index():
    current_user = session.get('user')
    return render_template('login.html', current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = request.form['password'].encode('utf-8')
            role = request.form['role']
            default_photo = 'profile_sementara.png'  # Use the default profile photo
            default_bio = "This is a default bio."
            nidn = request.form.get('nidn')
            nrp = request.form.get('nrp')
            prodi = request.form.get('prodi')

            print(f"Registering user: {name}, {email}, {role}, nidn: {nidn}, nrp: {nrp}")

            # Check for existing user
            existing_user = users_collection.find_one(
                {'$or': [{'name': name}, {'email': email}]})
            print(f"Existing user check: {existing_user}")

            if existing_user is None:
                hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
                print(f"Hashed password: {hashed_password}")

                # Insert user into users_collection
                user_data = {
                    'name': name,
                    'email': email,
                    'password': hashed_password,
                    'role': role,
                    'photo': default_photo,
                    'bio': default_bio
                }

                if role == 'peneliti':
                    user_data['nidn'] = nidn
                elif role == 'mahasiswa':
                    user_data['nrp'] = nrp
                    user_data['prodi'] = prodi

                print(f"User data to be inserted: {user_data}")

                user_id = users_collection.insert_one(user_data).inserted_id
                print(f"Inserted user ID: {user_id}")

                # Insert notification for the new user
                notification = {
                    'user_id': user_id,
                    'name': name,
                    'notifications': [{
                        'pemberitahuan': f"Registrasi berhasil pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                        'waktu': datetime.now(),
                        'status': 'belum dibaca'
                    }]
                }
                notifications_collection.insert_one(notification)

                return redirect(url_for('login'))
            else:
                return render_template('register.html', error='Name or email already exists')
        except Exception as e:
            print(f"Error during registration: {e}")
            return render_template('register.html', error='An error occurred. Please try again.')

    return render_template('register.html')


@app.route('/home')
def home():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})

        # Fetch all projects
        projects_data = list(projects_collection.find(
            {}, {'_id': 1, 'project_name': 1, 'project_creator': 1, 'status_penelitian': 1, 'email_creator': 1}
        ))

        # Custom sorting: "dalam perkembangannya" first, then "Selesai"
        def custom_sort_key(project):
            status_order = {
                "dalam perkembangannya": 1,
                "Selesai": 2
            }
            return status_order.get(project.get('status_penelitian', 'Selesai'), 3)

        # Sort projects by custom order
        projects_data.sort(key=custom_sort_key)

        notifications = list(notifications_collection.find({'user_id': user_id}))

        return render_template('home.html', user_data=user_data, projects_data=projects_data, notifications=notifications)
    else:
        return redirect(url_for('login'))



@app.route('/logout')
def logout():
    # Hapus data pengguna dari sesi saat logout
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user' in session:
        current_user = session['user']
        return render_template('profile.html', user=current_user)
    else:
        return redirect(url_for('login'))

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        success_flag = False

        if request.method == 'POST':
            new_name = request.form['name']
            new_email = request.form['email']
            new_role = request.form['role']
            new_bio = request.form['bio']

            existing_photo = request.form.get('existing_photo', None)

            new_photo = request.files['photo'] if 'photo' in request.files else None

            # proses upload file
            if new_photo:
                # menyimpan ke folder static
                filename = secure_filename(new_photo.filename)
                new_photo.save(f'static/{filename}')

                # upload ke field
                users_collection.update_one(
                    {'_id': user_id}, {'$set': {'photo': filename}})

            # update collection user
            result = users_collection.update_one(
                {'_id': user_id},
                {'$set': {'name': new_name, 'email': new_email,
                          'role': new_role, 'bio': new_bio}}
            )

            if result.modified_count > 0:
                success_flag = True

                # Perbarui data pengguna di sesi tersebut
                session['user']['name'] = new_name
                session['user']['email'] = new_email
                session['user']['role'] = new_role
                session['user']['bio'] = new_bio

                # Update notifications structure
                notification = {
                    'pemberitahuan': f"Profil Anda telah berhasil diperbarui pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                    'waktu': datetime.now(),
                    'status': 'belum dibaca'
                }
                notifications_collection.update_one(
                    {'user_id': user_id},
                    {'$push': {'notifications': notification}}
                )

        user_data = users_collection.find_one({'_id': user_id})
        return render_template('edit_profile.html', user=user_data, success_flag=success_flag)
    else:
        return redirect(url_for('login'))

@app.route('/get_user_data')
def get_user_data():
    if 'user' in session:
        user_id = ObjectId(session['user']['_id'])
        user_data = users_collection.find_one({'_id': user_id})
        return jsonify({'name': user_data['name'], 'email': user_data['email'], 'role': user_data['role']})
    else:
        return jsonify({'error': 'User not logged in'})

@app.route('/get_user_projects_data', methods=['GET'])
def get_user_projects_data():
    if 'user' in session:
        user_email = session['user']['email']
        user_data = users_collection.find_one({'email': user_email})
        user_role = user_data['role']
        user_name = user_data['name']

        print(f'User Email: {user_email}, User Name: {user_name}, User Role: {user_role}')  # Debugging

        # Query to find projects based on user role
        if user_role == 'admin' or user_role == 'admin peralatan':
            projects = projects_collection.find()
        else:
            projects = projects_collection.find({"member.email": user_email})

        project_list = list(projects)  # Convert cursor to list
        user_project_data = [{"_id": str(project['_id']), "project_name": project['project_name']} for project in project_list]

        print(f'Projects found: {user_project_data}')  # Debugging
        print(f'Raw Projects: {project_list}')  # More detailed debugging output

        return jsonify({"user_project_data": user_project_data})
    else:
        return jsonify({'error': 'User not logged in'})

@app.route('/borrow_equipment', methods=['GET', 'POST'])
def borrow_equipment_page():
    # Fetch equipment data including quantity
    equipment_data = list(equipment_collection.find(
        {}, {'_id': 0, 'name': 1, 'quantity': 1}))

    # Fetch user data
    user_id = ObjectId(session['user']['_id'])
    user_data = users_collection.find_one({'_id': user_id})
    user_name = user_data['name']
    # Assuming the user's email is stored in the 'email' field
    user_email = user_data['email']

    if request.method == 'POST':
        # Form for borrowing equipment
        equipment_name = request.form['equipment_name']
        requested_quantity = int(request.form['quantity'])
        borrow_date = request.form['borrow_date']
        return_date = request.form['return_date']

        # Prepare the email content
        email_subject = "Permintaan Peminjaman Peralatan"
        email_body = f"""
        Nama Peminjam: {user_name}
        Nama Peralatan: {equipment_name}
        Jumlah: {requested_quantity}
        Tanggal Pinjam: {borrow_date}
        Tanggal Kembali: {return_date}
        """

        # Prepare email for Sendinblue
        send_smtp_email = SendSmtpEmail(
            to=[SendSmtpEmailTo(email="211221002@mhs.stiki.ac.id")],
            sender=SendSmtpEmailSender(name=user_name, email=user_email),
            subject=email_subject,
            text_content=email_body
        )

        # Send the email
        try:
            api_instance.send_transac_email(send_smtp_email)

            # Insert the borrow request into the collection
            borrow_request = {
                'user_id': user_id,
                'user_name': user_name,
                'user_email': user_email,  # Include user's email in the request
                'equipment_name': equipment_name,
                'quantity': requested_quantity,
                'borrow_date': borrow_date,
                'return_date': return_date,
                'status': 'pending'  # You can add a status field to track the request status
            }
            borrowed_requests_collection.insert_one(borrow_request)

            # Add a notification for the user by appending to the notifications array
            notification = {
                'pemberitahuan': f"Permintaan peminjaman untuk {equipment_name} berhasil dikirim pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': user_id},
                {'$push': {'notifications': notification}}
            )

            flash('Permintaan peminjaman berhasil dikirim!', 'success')
        except Exception as e:
            flash(f'Gagal mengirim permintaan peminjaman: {e}', 'danger')

    return render_template('borrow_equipment.html', equipment=equipment_data, user_name=user_name)

@app.route('/newproject', methods=['GET', 'POST'])
def newproject():
    if 'user' in session:
        user_data = session['user']
        user_name = user_data['name']
        user_email = user_data['email']

        if request.method == 'POST':
            project_name = request.form['project_name']
            project_description = request.form['project_description']
            tanggal_mulai = request.form['tanggal_mulai']
            tanggal_selesai = request.form['tanggal_selesai']
            user_email = request.form['user_email']

            existing_project = projects_collection.find_one(
                {'project_name': project_name})

            if existing_project:
                flash(
                    'Project with this name already exists. Please choose a different name.', 'danger')
            else:
                project_description = request.form['project_description']

            member_data = {
                'name': user_name,
                'email': user_email,
                'role': 'Kepala Peneliti'
            }

            # Insert project into the database
            project_id = projects_collection.insert_one({
                'project_name': project_name,
                'project_description': project_description,
                'member': [member_data],
                'project_creator': user_name,
                'email_creator': user_email,
                'tanggal_mulai': tanggal_mulai,
                'tanggal_selesai': tanggal_selesai,
                'status_penelitian': 'dalam perkembangannya'
            }).inserted_id

            # Update user's projects
            users_collection.update_one(
                {'email': user_email},
                {'$addToSet': {'projects': {'_id': project_id, 'project_name': project_name}}}
            )

            # Create a group chat for the project
            group_chat_data = {
                'project_id': str(project_id),  # Convert ObjectId to string
                'project_name': project_name,
                # First message
                'messages': [{'sender': 'System', 'text': f'Selamat Group {project_name} Telah dibuat', 'timestamp': datetime.now()}],
                # Add the creator as a member
                'members': [{'email': user_email, 'name': user_name}]
            }
            messages_collection.insert_one(group_chat_data)

            # Add a notification for the user by appending to the notifications array
            notification = {
                'pemberitahuan': f'Project "{project_name}" telah berhasil dibuat pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': ObjectId(session['user']['_id'])},
                {'$push': {'notifications': notification}}
            )

            # Print data
            print(f"Project ID: {project_id}")

            flash('Project created successfully!', 'success')

        return render_template('newproject.html', user=user_data, user_email=user_email)
    else:
        return redirect(url_for('login'))

@app.route('/data')
def get_data():
    # Ambil semua data statistik dari koleksi
    all_data = statistik_collection.find()

    # Persiapkan data untuk dikirim sebagai respons JSON
    response_data = {
        'years': [],
        'counts': []
    }

    # Loop untuk mengumpulkan data dari setiap dokumen statistik
    for data in all_data:
        response_data['years'].append(str(data['tahun']))
        response_data['counts'].append(data['jumlah_project'])

    return jsonify(response_data)

@app.route('/statistik')
def statistik():
    return render_template('statistik.html')

@app.route('/sample')
def sample():
    # Ambil data sample dari koleksi MongoDB
    data_sample = list(sample_collection.find())
    return render_template('sample.html', data_sample=data_sample)

def get_project_creator_email(project_id):
    try:
        project = projects_collection.find_one({'_id': ObjectId(project_id)})
        if project:
            return project.get('email_creator')
        else:
            return None
    except Exception as e:
        print(f"Error retrieving project creator email: {str(e)}")
        return None

def calculate_deadline_task(end_date):
    # Convert string end_date to datetime object
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    # Get current date without time
    current_date = datetime.now().date()
    # Calculate the difference in days
    delta = (end_date_obj.date() - current_date).days

    if delta > 1:
        return f"{delta} hari lagi"
    elif delta == 1:
        return "Besok"
    elif delta == 0:
        return "Hari ini"
    else:
        return f"Sudah terlewat {abs(delta)} hari"

@app.route('/project/<project_id>', methods=['GET'])
def project_details(project_id):
    all_users = list(users_collection.find({"role": {"$ne": "admin"}}))
    project = projects_collection.find_one({'_id': ObjectId(project_id)})
    current_user = session.get('user')

    if current_user:
        # Fetch full user details if necessary
        current_user = users_collection.find_one(
            {'_id': ObjectId(current_user['_id'])})

    if project:
        schedules = project.get('schedules', [])
        tasks = project.get('tasks', [])
        members = project.get('member', [])
        # Ganti dengan logika sesuai dengan aplikasi Anda
        status_penelitian = project.get(
            'status_penelitian', 'Dalam Perkembangannya')

        if schedules:
            latest_end_date = max(schedule['end_date']
                                  for schedule in schedules)
            project['deadline'] = calculate_deadline_task(latest_end_date)
        else:
            project['deadline'] = "No schedules available"

        for task in tasks:
            task_name = task['name']
            matching_schedule = next(
                (schedule for schedule in schedules if schedule['activity_name'] == task_name), None)

            if task['status'] == 'Selesai':
                task['deadline'] = 'Selesai'
            elif matching_schedule:
                end_date = matching_schedule['end_date']
                task['deadline'] = calculate_deadline_task(end_date)
            else:
                task['deadline'] = "No matching schedule"

        return render_template('project_details.html', project=project, current_user=current_user, users=all_users, members=members, status_penelitian=status_penelitian)
    else:
        flash('Project not found')
        return redirect(url_for('index'))

@app.route('/update_task_status/<project_id>/<task_name>', methods=['POST'])
def update_task_status(project_id, task_name):
    current_user = session.get('user')
    if current_user['role'] not in ['admin', 'peneliti']:
        flash('Anda tidak memiliki izin untuk melakukan tindakan ini')
        return redirect(url_for('project_details', project_id=project_id))

    new_status = request.form.get('new_status')
    update_query = {'_id': ObjectId(project_id), 'tasks.name': task_name}
    update_fields = {'$set': {'tasks.$.status': new_status}}

    if new_status == 'Selesai':
        # Temukan tugas dan perbarui deadline menjadi "Selesai"
        project = projects_collection.find_one({'_id': ObjectId(project_id)})
        if project:
            tasks = project.get('tasks', [])
            for task in tasks:
                if task['name'] == task_name:
                    task['deadline'] = 'Selesai'
                    break
            projects_collection.update_one(
                update_query, {'$set': {'tasks.$.deadline': 'Selesai'}})
    else:
        # Pastikan deadline dihitung ulang
        project = projects_collection.find_one({'_id': ObjectId(project_id)})
        if project:
            schedules = project.get('schedules', [])
            matching_schedule = next(
                (schedule for schedule in schedules if schedule['activity_name'] == task_name), None)
            if matching_schedule:
                end_date = matching_schedule['end_date']
                deadline = calculate_deadline_task(end_date)
                projects_collection.update_one(
                    update_query, {'$set': {'tasks.$.deadline': deadline}})

    projects_collection.update_one(update_query, update_fields)

    # Tambahkan notifikasi untuk pembaruan status tugas
    notification = {
        'pemberitahuan': f'Status tugas {task_name} pada proyek {project_id} telah diperbarui menjadi {new_status}.',
        'waktu': datetime.now(),
        'status': 'belum dibaca'
    }
    notifications_collection.update_one(
        {'user_id': ObjectId(current_user['_id'])},
        {'$push': {'notifications': notification}}
    )

    flash('Status tugas berhasil diperbarui')
    return redirect(url_for('project_details', project_id=project_id))

def calculate_progress(project):
    total_tasks = len(project.get('tasks', []))
    completed_tasks = len([task for task in project.get(
        'tasks', []) if task.get('status') == 'Selesai'])
    return (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

@app.route('/myproject')
def myproject():
    if 'user' in session:
        current_user_email = session['user']['email']
        user_role = session['user']['role']

        if user_role == 'admin':
            my_projects = projects_collection.find()
        else:
            my_projects = projects_collection.find(
                {'member.email': current_user_email})

        # Ubah tanggal_selesai menjadi objek datetime.date
        my_projects = [
            {
                **project,
                '_id': str(project['_id']),
                'deadline': calculate_deadline(project['tanggal_selesai']),
                # Exclude the head researcher
                'members': [member['name'] for member in project['member'] if member['name'] != project['project_creator']],
                'progress': calculate_progress(project)
            } for project in my_projects
        ]

        # Sorting projects by nearest deadline
        my_projects_sorted = sorted(my_projects, key=lambda x: datetime.strptime(
            x['tanggal_selesai'], '%Y-%m-%d').date())

        return render_template('myproject.html', my_projects=my_projects_sorted)
    else:
        return redirect(url_for('login'))

@app.route('/get_user_projects', methods=['GET'])
def get_user_projects():
    if 'user' in session:
        user_email = session['user']['email']
        projects = list(projects_collection.find(
            {'members.email': user_email}, {'_id': 1, 'project_name': 1}))
        for project in projects:
            project['_id'] = str(project['_id'])
        return jsonify(projects)
    else:
        return jsonify([])  # Return empty list if user not logged in

@app.route('/chat/messages', methods=['GET'])
def get_chat_messages():
    project_id = request.args.get('project_id')
    project_name = request.args.get('project_name')
    messages = messages_collection.find_one(
        {"project_id": project_id, "project_name": project_name})

    if messages:
        return jsonify(messages)
    else:
        return jsonify({"messages": []})

@app.route('/get_project_messages/<project_id>', methods=['GET'])
def get_project_messages(project_id):
    project_messages = messages_collection.find_one({'project_id': project_id})
    if project_messages:
        print(project_messages)  # Tambahkan log ini
        return jsonify({'messages': project_messages['messages']})
    else:
        print("No messages found")  # Tambahkan log ini
        return jsonify({'messages': []})

@app.route('/get_chat_history', methods=['GET'])
def get_chat_history():
    project_id = request.args.get('projectId')
    if not project_id:
        return jsonify({"error": "projectId is required"}), 400

    # Temukan dokumen dengan project_id yang sesuai dalam koleksi messages
    project = messages_collection.find_one({"project_id": project_id})
    if project:
        # Ambil array messages dari proyek
        messages = project.get('messages', [])
        return jsonify({"messages": messages})
    return jsonify({"error": "Project not found"}), 404

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json

    # Check if 'message' and 'project_id' are in the request data
    if 'message' in data and 'project_id' in data:
        message = data['message']
        project_id = data['project_id']
        current_user = session.get('user')

        # Check if the user is logged in
        if current_user is None:
            return jsonify({"success": False, "message": "User not logged in"}), 401

        # Get current timestamp in WIB
        tz_wib = pytz.timezone('Asia/Jakarta')
        timestamp = datetime.now(tz_wib)

        # Find the document with the given project_id
        project = messages_collection.find_one({"project_id": project_id})

        if project:
            # Update the document by pushing the new message to the 'messages' array
            messages_collection.update_one(
                {"project_id": project_id},
                {"$push": {"messages": {"text": message,
                                        "sender": current_user['name'], "timestamp": timestamp}}}
            )
            # Print the message for debugging
            print("Pesan yang diterima:", message)
            print("user:", current_user['name'])
            print("timestamp:", timestamp)
            return jsonify({"success": True, "message": message, "sender": current_user['name'], "timestamp": timestamp.isoformat()}), 200
        else:
            return jsonify({"success": False, "message": "Project ID tidak ditemukan"}), 404
    else:
        return jsonify({"success": False, "message": "Gagal mengirim pesan. Data tidak lengkap"}), 400

@app.route('/send_join_request', methods=['POST'])
def send_join_request():
    full_name = request.form.get('namaLengkap')
    email = request.form.get('alamatEmail')
    role = request.form.get('posisi') 
    special_message = request.form.get('pesanKhusus')
    creator_email = request.form.get('creatorEmail')
    project_name = request.form.get('projectName')

    # Check if the user is already a member of the project
    project = projects_collection.find_one({
        'project_name': project_name,
        'member.email': email
    })
    
    if project:
        return jsonify({'status': 'error', 'message': 'Anda sudah menjadi anggota proyek ini!'})


    # Generate unique tokens for acceptance and rejection
    accept_token = str(ObjectId())
    reject_token = str(ObjectId())

    # Prepare the email content
    subject = f"Permohonan Bergabung pada Proyek: {project_name}"
    body = f"""
    Yth. Kepala Peneliti,

    Dengan hormat,

    Kami ingin menginformasikan bahwa Anda telah menerima permohonan untuk bergabung dengan proyek penelitian Anda yang berjudul "{project_name}". Permohonan ini diajukan oleh individu yang berminat untuk turut serta dalam penelitian dan memberikan kontribusi sesuai dengan posisi yang dilamar.

    Berikut adalah informasi detail mengenai permohonan tersebut:
    - Nama Lengkap: {full_name}
    - Alamat Email: {email}
    - Posisi yang Diminta: {role}
    - Pesan Khusus: {special_message}

    Kami menghargai waktu dan perhatian Anda dalam menilai permohonan ini. Untuk melanjutkan proses, silakan pilih salah satu dari tautan di bawah ini sesuai dengan keputusan Anda:
    - <a href="{url_for('accept_request', token=accept_token, _external=True)}">Terima Permohonan</a>: Jika Anda setuju untuk menerima permohonan ini dan mengizinkan individu tersebut untuk bergabung dengan proyek Anda.
    - <a href="{url_for('reject_request', token=reject_token, _external=True)}">Tolak Permohonan</a>: Jika Anda memutuskan untuk menolak permohonan ini dan tidak melanjutkan proses lebih lanjut.

    Kami sangat menghargai keputusan Anda dan berharap permohonan ini mendapatkan perhatian yang layak. Apabila ada pertanyaan atau membutuhkan informasi tambahan, jangan ragu untuk menghubungi kami.

    Terima kasih atas kerjasama dan dukungan Anda dalam proses ini. Kami menantikan tanggapan Anda dan berharap proyek penelitian ini dapat terus berkembang dengan kontribusi yang berarti.

    Hormat kami,
    Web Labs
    """

    # Send the email using Sendinblue API
    sender = SendSmtpEmailSender(email='211221002@mhs.stiki.ac.id', name='Web Labs')
    to = SendSmtpEmailTo(email=creator_email, name='Kepala Peneliti')
    email_content = SendSmtpEmail(
        sender=sender,
        to=[to],
        subject=subject,
        html_content=body
    )

    try:
        api_instance.send_transac_email(email_content)
        # Store the tokens for later use
        tokens_collection.insert_one({
            'accept_token': accept_token,
            'reject_token': reject_token,
            'request_data': {
                'full_name': full_name,
                'email': email,
                'role': role,
                'special_message': special_message,
                'creator_email': creator_email,
                'project_name': project_name
            }
        })
        return jsonify({'status': 'success', 'message': 'Permohonan bergabung berhasil dikirim!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gagal mengirim email: {str(e)}'})

@app.route('/accept_request/<token>', methods=['GET'])
def accept_request(token):
    # Ambil data token dari koleksi tokens
    token_data = tokens_collection.find_one({'accept_token': token})

    if token_data:
        request_data = token_data['request_data']
        project_name = request_data['project_name']
        user_email = request_data['email']
        
        # Struktur data anggota baru
        new_member = {
            'name': request_data['full_name'],
            'email': user_email,
            'role': request_data['role']  # Gunakan field role
        }
        
        # Temukan proyek dan tambahkan pengguna ke anggota proyek
        projects_collection.update_one(
            {'project_name': project_name},
            {'$push': {'member': new_member}}
        )
        
        # Kirim email konfirmasi kepada pengguna
        subject = f"Konfirmasi Penerimaan Permohonan Bergabung pada Proyek '{project_name}'"
        body = f"""
        Yth. {request_data['full_name']},

        Dengan hormat,

        Kami ingin memberitahukan bahwa permohonan Anda untuk bergabung dengan proyek penelitian yang berjudul "{project_name}" telah kami terima dan setujui. Kami sangat menghargai minat dan kesediaan Anda untuk memberikan kontribusi dalam proyek ini.

        Anda sekarang telah resmi menjadi anggota proyek tersebut, dan kami berharap kehadiran Anda akan membawa dampak positif bagi perkembangan penelitian ini.

        Apabila Anda memiliki pertanyaan lebih lanjut atau membutuhkan informasi tambahan, jangan ragu untuk menghubungi kami. Kami akan dengan senang hati membantu Anda.

        Terima kasih atas perhatian dan partisipasi Anda.

        Salam hormat,
        Web Labs
        """
        send_email(request_data['email'], subject, body)

        # Beritahu Kepala Peneliti tentang penerimaan permohonan
        subject = f"Pemberitahuan Penerimaan Permohonan Bergabung pada Proyek '{project_name}'"
        body = f"""
        Yth. Kepala Peneliti,

        Dengan ini kami informasikan bahwa permohonan untuk bergabung dengan proyek penelitian yang berjudul "{project_name}" dari {request_data['full_name']} telah diterima dan disetujui. 

        Kami berharap bahwa penambahan anggota baru ini akan memberikan kontribusi yang signifikan dalam kemajuan proyek dan penelitian yang sedang berlangsung.

        Kami mengucapkan terima kasih atas perhatian dan kerjasama Anda dalam proses ini. Jika Anda memerlukan informasi lebih lanjut atau ada hal lain yang perlu didiskusikan, jangan ragu untuk menghubungi kami.

        Salam hormat,
        Web Labs
        """
        send_email(request_data['creator_email'], subject, body)

        # Hapus entri token
        tokens_collection.delete_one({'accept_token': token})

        return "Permohonan Anda telah diterima dan diproses dengan baik. Kami telah mengirimkan konfirmasi kepada Anda melalui email."

    return "Token yang Anda gunakan tidak valid atau telah kedaluwarsa. Mohon periksa kembali dan coba lagi."

@app.route('/reject_request/<token>', methods=['GET'])
def reject_request(token):
    # Ambil data token dari koleksi tokens
    token_data = tokens_collection.find_one({'reject_token': token})

    if token_data:
        request_data = token_data['request_data']
        project_name = request_data['project_name']

        # Kirim email penolakan kepada pengguna
        subject = f"Permohonan Bergabung Anda pada Proyek '{project_name}'"
        body = f"""
        Yth. {request_data['full_name']},

        Dengan hormat,

        Kami ingin memberitahukan bahwa permohonan Anda untuk bergabung dengan proyek penelitian yang berjudul "{project_name}" telah kami pertimbangkan dengan seksama. Namun, setelah evaluasi, kami mohon maaf karena permohonan Anda tidak dapat kami terima saat ini.

        Kami sangat menghargai minat Anda untuk berkontribusi dalam proyek ini dan berharap Anda tidak merasa kecewa. Kami mendorong Anda untuk tetap bersemangat dan terus mencari peluang lain yang mungkin sesuai dengan minat dan keahlian Anda.

        Terima kasih atas perhatian dan partisipasi Anda. Jika ada pertanyaan atau jika Anda membutuhkan informasi lebih lanjut, jangan ragu untuk menghubungi kami.

        Salam hormat,
        Web Labs
        """
        send_email(request_data['email'], subject, body)

        # Beritahu Kepala Peneliti tentang penolakan permohonan
        subject = f"Penolakan Permohonan Bergabung pada Proyek '{project_name}'"
        body = f"""
        Yth. Kepala Peneliti,

        Kami ingin menginformasikan bahwa permohonan untuk bergabung dengan proyek penelitian yang berjudul "{project_name}" dari {request_data['full_name']} telah ditolak.

        Kami menghargai waktu dan perhatian Anda dalam menangani permohonan ini. Jika ada pertanyaan lebih lanjut atau hal lain yang perlu didiskusikan, jangan ragu untuk menghubungi kami.

        Terima kasih atas kerjasama dan dukungan Anda.

        Salam hormat,
        Web Labs
        """
        send_email(request_data['creator_email'], subject, body)

        # Hapus entri token
        tokens_collection.delete_one({'reject_token': token})

        return "Permohonan Anda telah ditolak dan kami telah mengirimkan pemberitahuan melalui email."

    return "Token yang Anda gunakan tidak valid atau telah kedaluwarsa. Mohon periksa kembali dan coba lagi."

def send_email(to_email, subject, body):
    sender = SendSmtpEmailSender(email='211221002@mhs.stiki.ac.id', name='Web Labs')
    to = SendSmtpEmailTo(email=to_email)
    email_content = SendSmtpEmail(
        sender=sender,
        to=[to],
        subject=subject,
        html_content=body
    )
    
    try:
        api_instance.send_transac_email(email_content)
    except Exception as e:
        print(f"Error sending email: {str(e)}")

@app.route('/save_to_project', methods=['POST'])
def save_to_project():
    data = request.json

    # Mengambil data yang diperlukan
    namaLengkap = data.get('namaLengkap')
    alamatEmail = data.get('alamatEmail')
    posisi = data.get('posisi')

    # Data yang akan disimpan ke dalam array member
    member_data = {
        'namaLengkap': namaLengkap,
        'alamatEmail': alamatEmail,
        'posisi': posisi
    }

    # Menggunakan MongoDB untuk menyimpan data ke dalam collection project di array member
    try:
        # Query untuk menemukan dokumen yang sesuai dengan kriteria Anda
        # Ganti 'nama_proyek' dengan kriteria yang sesuai
        query = {'project_name': 'nama_proyek'}
        # Operasi untuk menambahkan data ke dalam array member
        update_query = {'$push': {'members': member_data}}
        # Melakukan update ke dalam collection
        result = projects_collection.update_one(query, update_query)

        if result.matched_count == 0:
            return jsonify({'message': 'Proyek tidak ditemukan'}), 404

        return jsonify({'message': 'Data berhasil disimpan ke dalam collection project di array member'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_task', methods=['POST'])
def add_task():
    project_id = request.form['project_id']
    task_name = request.form['task_name']
    task_assignee = request.form['task_assignee']
    task_status = request.form['task_status']

    new_task = {
        'name': task_name,
        'assigned_to': task_assignee,
        'status': task_status
    }

    projects_collection.update_one(
        {'_id': ObjectId(project_id)},
        {'$push': {'tasks': new_task}}
    )

    # Tambahkan notifikasi untuk penambahan tugas kepada pengguna yang ditugaskan
    notification_task_assigned = {
        'pemberitahuan': f'Anda telah ditugaskan untuk tugas baru "{task_name}" dalam proyek {project_id}.',
        'waktu': datetime.now(),
        'status': 'belum dibaca'
    }

    # Simpan notifikasi ke dalam koleksi notifikasi untuk pengguna yang ditugaskan
    notifications_collection.update_one(
        {'user_id': ObjectId(task_assignee)},
        {'$push': {'notifications': notification_task_assigned}}
    )

    # Tambahkan notifikasi umum untuk penambahan tugas
    notification_task_added = {
        'pemberitahuan': f'Tugas baru "{task_name}" telah ditambahkan ke dalam proyek {project_id}.',
        'waktu': datetime.now(),
        'status': 'belum dibaca'
    }

    # Simpan notifikasi umum ke dalam koleksi notifikasi untuk pengguna terkait
    current_user = session.get('user')
    notifications_collection.update_one(
        {'user_id': ObjectId(current_user['_id'])},
        {'$push': {'notifications': notification_task_added}}
    )

    return redirect(url_for('project_details', project_id=project_id))

@app.route('/upload_file/<project_id>/<task_name>', methods=['POST'])
def upload_file(project_id, task_name):
    if 'file' not in request.files:
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        return redirect(request.url)

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # Ambil dokumen proyek dari database
        project = projects_collection.find_one({'_id': ObjectId(project_id)})

        # Perbarui file path di tugas yang sesuai dengan nama tugas
        for task in project['tasks']:
            if task['name'] == task_name:
                task['file'] = file_path
                break

        # Perbarui dokumen proyek di database
        projects_collection.update_one(
            {'_id': ObjectId(project_id)},
            {'$set': {'tasks': project['tasks']}}
        )

        # Tambahkan notifikasi untuk pengguna terkait
        notification = {
            'pemberitahuan': f'File baru "{filename}" telah diunggah ke tugas "{task_name}" dalam proyek {project_id}.',
            'waktu': datetime.now(),
            'status': 'belum dibaca'
        }

        # Simpan notifikasi ke dalam koleksi notifikasi untuk pengguna terkait
        current_user = session.get('user')
        notifications_collection.update_one(
            {'user_id': ObjectId(current_user['_id'])},
            {'$push': {'notifications': notification}}
        )

        return redirect(url_for('project_details', project_id=project_id))

@app.route('/view_file/<path:filename>')
def view_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/send_member_email', methods=['POST'])
def send_member_email():
    sender_email = '211221002@mhs.stiki.ac.id'
    try:
        # Mendapatkan data dari permintaan
        data = request.json

        # Generate random token for acceptance and rejection
        accept_token = str(ObjectId())
        reject_token = str(ObjectId())

        # Save tokens in the database with an expiration time
        tokens_collection.insert_one({
            "email": data['member_email'],
            "accept_token": accept_token,
            "reject_token": reject_token,
            "expiration": datetime.now() + timedelta(days=3),  # Token valid for 3 days
            "project_id": data['project_id'],
            "member_name": data['member_name'],
            "member_role": data['member_role']
        })

        # Create acceptance and rejection links
        accept_link = url_for('accept_invitation',
                              token=accept_token, _external=True)
        reject_link = url_for('reject_invitation',
                              token=reject_token, _external=True)

        # Membuat objek email yang akan dikirim
        email = SendSmtpEmail(
            sender=SendSmtpEmailSender(name="Web Lab", email=sender_email),
            to=[SendSmtpEmailTo(email=data['member_email'],
                                name=data['member_name'])],
            subject="You've been added to a team",
            html_content=f"<html><body>Anda Telah Diundang untuk Mengikuti Penelitian dengan posisi yaitu {data['member_role']} di dalam team apakah anda menerima atau tidak.<br>Jika iya tekan link dibawah ini:<br><a href='{accept_link}'>Terima</a><br>Jika tidak maka klik link dibawah ini:<br><a href='{reject_link}'>Tolak</a></body></html>"
        )

        # Mengirim email transaksional
        api_response = api_instance.send_transac_email(email)

        # Add a notification for the user by appending to the notifications array
        notification = {
            'pemberitahuan': f'Anda telah diundang untuk bergabung dalam proyek dengan posisi {data["member_role"]} pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
            'waktu': datetime.now(),
            'status': 'belum dibaca'
        }
        notifications_collection.update_one(
            {'user_id': ObjectId(session['user']['_id'])},
            {'$push': {'notifications': notification}}
        )

        # Mengembalikan respons
        return jsonify({"success": True, "message": "Email sent successfully.", "message_id": api_response.message_id}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/accept_invitation/<token>', methods=['GET'])
def accept_invitation(token):
    token_data = tokens_collection.find_one({"accept_token": token})
    if token_data and token_data['expiration'] > datetime.now():
        # Update the project collection with the member's data
        project_id = token_data['project_id']
        member_email = token_data['email']
        member_name = token_data['member_name']
        member_role = token_data['member_role']

        projects_collection.update_one(
            {"_id": ObjectId(project_id)},
            {"$push": {"member": {"email": member_email,
                                  "name": member_name, "role": member_role}}}
        )

        return jsonify({"success": True, "message": "You have successfully accepted the invitation."}), 200
    else:
        return jsonify({"success": False, "message": "Invalid or expired token."}), 400

@app.route('/reject_invitation/<token>', methods=['GET'])
def reject_invitation(token):
    token_data = tokens_collection.find_one({"reject_token": token})
    if token_data and token_data['expiration'] > datetime.now():
        # Mengambil informasi proyek untuk mendapatkan email kepala peneliti
        project_data = projects_collection.find_one(
            {"_id": ObjectId(token_data['project_id'])})
        if not project_data:
            return jsonify({"success": False, "message": "Project not found."}), 404

        # Mencari email kepala peneliti dalam daftar anggota
        leader_email = None
        for member in project_data['member']:
            if member['role'] == 'Kepala Peneliti':
                leader_email = member['email']
                break

        if not leader_email:
            return jsonify({"success": False, "message": "Leader email not found in project members."}), 404

        # Mengirim email penolakan kepada kepala peneliti
        rejection_email = SendSmtpEmail(
            sender=SendSmtpEmailSender(name="Web Lab", email=leader_email),
            to=[SendSmtpEmailTo(email=leader_email)],
            subject="Invitation Rejected",
            html_content=f"<html><body>{token_data['email']} telah menolak undangan untuk bergabung dengan tim.</body></html>"
        )
        api_instance.send_transac_email(rejection_email)

        return jsonify({"success": True, "message": "You have successfully rejected the invitation."}), 200
    else:
        return jsonify({"success": False, "message": "Invalid or expired token."}), 400

@app.route('/add_schedule/<project_id>', methods=['POST'])
def add_schedule(project_id):
    # Mendapatkan data dari request JSON
    data = request.get_json()
    schedule_activity_name = data.get('schedule_activity_name')
    schedule_assigned_to = data.get('schedule_assigned_to')
    schedule_start_date = data.get('schedule_start_date')
    schedule_end_date = data.get('schedule_end_date')

    # Memastikan project_id valid
    if not ObjectId.is_valid(project_id):
        return jsonify({'message': 'Invalid project ID'}), 400

    project = projects_collection.find_one({'_id': ObjectId(project_id)})

    if not project:
        return jsonify({'message': 'Project not found'}), 404

    # Membuat dokumen jadwal
    schedule_data = {
        'activity_name': schedule_activity_name,
        'assigned_to': schedule_assigned_to,
        'start_date': schedule_start_date,
        'end_date': schedule_end_date
    }

    # Memeriksa apakah jadwal dengan nama aktivitas yang sama sudah ada dalam proyek ini
    existing_schedule = next((schedule for schedule in project.get(
        'schedules', []) if schedule['activity_name'] == schedule_activity_name), None)

    if existing_schedule:
        # Jika jadwal sudah ada, perbarui
        projects_collection.update_one(
            {'_id': ObjectId(project_id),
             'schedules.activity_name': schedule_activity_name},
            {'$set': {'schedules.$': schedule_data}}
        )
        message = 'Schedule updated successfully'
    else:
        # Jika jadwal tidak ada, tambahkan
        projects_collection.update_one(
            {'_id': ObjectId(project_id)},
            {'$push': {'schedules': schedule_data}}
        )
        message = 'Schedule added successfully'

        # Tambahkan notifikasi untuk pengguna terkait
        notification = {
            'pemberitahuan': f'Jadwal baru "{schedule_activity_name}" telah ditambahkan ke dalam proyek {project_id} pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
            'waktu': datetime.now(),
            'status': 'belum dibaca'
        }

        # Simpan notifikasi ke dalam koleksi notifikasi untuk pengguna terkait
        current_user = session.get('user')
        notifications_collection.update_one(
            {'user_id': ObjectId(current_user['_id'])},
            {'$push': {'notifications': notification}}
        )

    # Respon dengan pesan sukses dan data jadwal yang ditambahkan atau diperbarui
    return jsonify({'message': message, 'schedule': schedule_data}), 200

@app.route('/edit_project/<project_id>', methods=['POST'])
def edit_project(project_id):
    data = request.json

    # Validate the project ID
    try:
        project_id = ObjectId(project_id)
    except:
        return jsonify({"message": "Invalid project ID"}), 400

    # Find and update the project
    result = projects_collection.update_one(
        {"_id": project_id},
        {"$set": {
            "project_name": data.get("project_name"),
            "project_creator": data.get("project_creator"),
            "project_description": data.get("project_description"),
            "goals": data.get("project_goals")
        }}
    )

    if result.matched_count == 0:
        return jsonify({"message": "Project not found"}), 404

    # Add a notification for project update
    notification = {
        'pemberitahuan': f'Proyek {data.get("project_name")} telah diperbarui pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
        'waktu': datetime.now(),
        'status': 'belum dibaca'
    }

    # Save the notification to the notifications collection for related users
    current_user = session.get('user')
    notifications_collection.update_one(
        {'user_id': ObjectId(current_user['_id'])},
        {'$push': {'notifications': notification}}
    )

    return jsonify({"message": "Project updated successfully"}), 200

@app.route('/update_project_status/<project_id>', methods=['POST'])
def update_project_status(project_id):
    # Ensure the user is an admin
    if not session.get('is_admin'):
        return redirect(url_for('index'))

    new_status = request.form.get('project_status')
    if new_status:
        # Update the project status in the database
        projects_collection.update_one(
            {'_id': ObjectId(project_id)},
            {'$set': {'project_status': new_status}}
        )

        # Create a notification for project status update
        notification = {
            'pemberitahuan': f'Status proyek telah diperbarui menjadi {new_status} pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
            'waktu': datetime.now(),
            'status': 'belum dibaca'
        }

        notifications_collection.insert_one(notification)
    return redirect(url_for('index'))

@app.route('/delete_project_by_name/<string:project_name>', methods=['DELETE'])
def delete_project_by_name(project_name):
    # Find and delete the project by project_name
    result = projects_collection.delete_one({"project_name": project_name})

    if result.deleted_count == 1:
        return jsonify({"message": f"Project '{project_name}' deleted successfully"}), 200
    else:
        return jsonify({"error": "Project not found"}), 404


@app.route('/manage_borrow_requests', methods=['GET', 'POST'])
def manage_borrow_requests():
    # Ambil semua permintaan peminjaman dari koleksi borrowed_requests
    borrow_requests = list(borrowed_requests_collection.find({}))

    # Sortir permintaan peminjaman dengan status 'pending' paling atas
    borrow_requests.sort(key=lambda x: x['status'] != 'pending')

    return render_template('manage_borrow_requests.html', borrow_requests=borrow_requests)

@app.route('/update_borrow_request/<request_id>', methods=['POST', 'GET'])
def update_borrow_request(request_id):
    if request.method == 'POST':
        action = request.form.get('action')
        reason = request.form.get('reason', '')

        borrow_request = borrowed_requests_collection.find_one(
            {'_id': ObjectId(request_id)})

        user_id = borrow_request['user_id']
        user_email = borrow_request['user_email']
        equipment_name = borrow_request['equipment_name']

        if action == 'accept':
            borrowed_requests_collection.update_one(
                {'_id': ObjectId(request_id)}, {'$set': {'status': 'accepted'}})
            borrowed_equipment_collection.insert_one({
                'user_email': user_email,
                'user_name': borrow_request['user_name'],
                'equipment_name': equipment_name,
                'quantity': borrow_request['quantity'],
                'borrow_date': borrow_request['borrow_date'],
                'return_date': borrow_request['return_date'],
                'status': 'accepted'
            })

            # Add notification for accepted request
            notification = {
                'pemberitahuan': f'Permintaan peminjaman untuk {equipment_name} telah diterima pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': user_id},
                {'$push': {'notifications': notification}}
            )

            flash('Borrow request accepted.', 'success')
        elif action == 'reject':
            equipment_collection.update_one(
                {'name': equipment_name}, {'$inc': {'quantity': borrow_request['quantity']}})
            borrowed_requests_collection.update_one(
                {'_id': ObjectId(request_id)}, {'$set': {'status': 'rejected'}})

            # Add notification for rejected request
            notification = {
                'pemberitahuan': f'Permintaan peminjaman untuk {equipment_name} telah ditolak pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}. Alasan: {reason}',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': user_id},
                {'$push': {'notifications': notification}}
            )

            # Send rejection email using Sendinblue
            sender = SendSmtpEmailSender(
                name="Your Name", email="211221002@mhs.stiki.ac.id")
            to = [SendSmtpEmailTo(email=user_email)]
            subject = "Borrow Request Rejected"
            html_content = f"<p>Your borrow request for {equipment_name} has been rejected.</p><p>Reason: {reason}</p>"
            email = SendSmtpEmail(sender=sender, to=to,
                                  subject=subject, html_content=html_content)

            try:
                api_instance.send_transac_email(email)
                flash(
                    'Borrow request rejected and equipment quantity restored. Reason sent via email.', 'success')
            except Exception as e:
                flash(f'Failed to send email: {e}', 'danger')

    return redirect(url_for('manage_borrow_requests'))

def calculate_deadline(return_date):
    today = datetime.today().date()
    return_date = datetime.strptime(return_date, '%Y-%m-%d').date()
    diff_days = (return_date - today).days

    if diff_days > 0:
        return f"{diff_days} hari tersisa"
    elif diff_days == 0:
        return "Hari ini"
    else:
        return "Sudah lewat"

@app.route('/borrowed_equipment')
def borrowed_equipment():
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to be logged in to view this page.', 'danger')
        return redirect(url_for('login'))

    borrowed_equipment = borrowed_equipment_collection.find(
        {'user_id': ObjectId(user_id)})
    borrowed_equipment_list = []
    for equipment in borrowed_equipment:
        if 'return_date' in equipment:
            equipment['deadline'] = calculate_deadline(
                equipment['return_date'])
            equipment['days_until_return'] = (datetime.strptime(
                equipment['return_date'], '%Y-%m-%d').date() - datetime.today().date()).days
        else:
            equipment['deadline'] = 'Tanggal kembali tidak tersedia'
            # Menempatkan item tanpa return_date di bagian bawah
            equipment['days_until_return'] = float('inf')
        borrowed_equipment_list.append(equipment)

    borrowed_equipment_list.sort(key=lambda x: x['days_until_return'])

    return render_template('borrowed_equipment.html', borrowed_equipment=borrowed_equipment_list)

@app.route('/manage_equipment', methods=['GET', 'POST'])
def manage_equipment():
    if request.method == 'POST':
        name = request.form.get('name')
        quantity = request.form.get('quantity')
        equipment_id = request.form.get('equipment_id')

        if not name or not quantity:
            flash('Nama dan jumlah peralatan harus diisi.', 'danger')
        else:
            if equipment_id:
                equipment = equipment_collection.find_one(
                    {'_id': ObjectId(equipment_id)})
                if equipment:
                    # Update existing equipment
                    equipment_collection.update_one(
                        {'_id': ObjectId(equipment_id)},
                        {'$set': {'name': name, 'quantity': int(quantity)}}
                    )
                    flash('Peralatan berhasil diperbarui.', 'success')

                    # Create notification for equipment update
                    notification = {
                        'pemberitahuan': f'Peralatan {equipment["name"]} telah diperbarui dengan jumlah {quantity}.',
                        'waktu': datetime.now(),
                        'status': 'belum dibaca'
                    }
                    notifications_collection.update_one(
                        {'user_id': ObjectId(session['user']['_id'])},
                        {'$push': {'notifications': notification}}
                    )

                else:
                    flash('Peralatan tidak ditemukan.', 'danger')
            else:
                # Add new equipment
                new_equipment = {
                    'name': name,
                    'quantity': int(quantity)
                }
                equipment_collection.insert_one(new_equipment)
                flash('Peralatan berhasil ditambahkan.', 'success')

                # Create notification for new equipment
                notification = {
                    'pemberitahuan': f'Peralatan baru {name} telah ditambahkan dengan jumlah {quantity}.',
                    'waktu': datetime.now(),
                    'status': 'belum dibaca'
                }
                notifications_collection.update_one(
                    {'user_id': ObjectId(session['user']['_id'])},
                    {'$push': {'notifications': notification}}
                )

    equipment_list = equipment_collection.find()
    return render_template('manage_equipment.html', equipment_list=equipment_list)

@app.route('/delete_equipment/<equipment_id>', methods=['POST'])
def delete_equipment(equipment_id):
    equipment_collection.delete_one({'_id': ObjectId(equipment_id)})
    flash('Peralatan berhasil dihapus.', 'success')
    return redirect(url_for('manage_equipment'))

@app.route('/add_equipment', methods=['GET', 'POST'])
def add_equipment():
    if request.method == 'POST':
        name = request.form.get('name')
        quantity = request.form.get('quantity')

        if not name or not quantity:
            flash('Nama dan jumlah peralatan harus diisi.', 'danger')
        else:
            new_equipment = {
                'name': name,
                'quantity': int(quantity)
            }
            equipment_collection.insert_one(new_equipment)
            flash('Peralatan berhasil ditambahkan.', 'success')

            # Create notification for new equipment
            notification = {
                'pemberitahuan': f'Peralatan baru {name} telah ditambahkan dengan jumlah {quantity}.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': ObjectId(session['user']['_id'])},
                {'$push': {'notifications': notification}}
            )
            return redirect(url_for('manage_equipment'))

    return render_template('add_equipment.html')

@app.route('/edit_equipment', methods=['POST'])
def edit_equipment():
    equipment_id = request.form.get('equipment_id')
    name = request.form.get('name')
    quantity = request.form.get('quantity')

    if not equipment_id or not name or not quantity:
        flash('Semua field harus diisi.', 'danger')
    else:
        equipment_collection.update_one(
            {'_id': ObjectId(equipment_id)},
            {'$set': {'name': name, 'quantity': int(quantity)}}
        )
        flash('Peralatan berhasil diupdate.', 'success')

        # Create a notification for equipment update
        notification = {
            'pemberitahuan': f'Peralatan {name} telah diperbarui pada {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.',
            'waktu': datetime.now(),
            'status': 'belum dibaca'
        }
        notifications_collection.insert_one(notification)

    return redirect(url_for('manage_equipment'))

@app.route('/project/<project_id>/progress')
def project_progress(project_id):
    project = projects_collection.find_one({"_id": ObjectId(project_id)})
    if not project:
        return jsonify({"message": "Project not found"}), 404

    total_tasks = len(project.get("tasks", []))
    completed_tasks = len([task for task in project.get(
        "tasks", []) if task.get("status") == "Selesai"])

    progress_percentage = (completed_tasks / total_tasks) * \
        100 if total_tasks > 0 else 0

    return jsonify({"progress": progress_percentage})

@app.route('/project/<project_id>/complete', methods=['POST'])
def complete_project(project_id):
    # Mendapatkan status proyek yang baru dari request JSON
    new_status = request.json.get('status_penelitian', 'Selesai')

    # Mengupdate status proyek di collection project
    result = projects_collection.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status_penelitian": new_status}}
    )

    if result.modified_count == 1:
        if new_status == 'Selesai':
            # Ambil dokumen proyek dari database
            project = projects_collection.find_one(
                {'_id': ObjectId(project_id)})

            # Loop untuk memindahkan file yang diupload ke koleksi sample
            for task in project['tasks']:
                if 'file' in task:
                    sample_filter = {
                        'project_id': project_id,
                        'task_name': task['name']
                    }
                    sample_document = {
                        'project_id': project_id,
                        'project_name': project['project_name'],
                        'uploader': task['assigned_to'],
                        'task_name': task['name'],
                        'file_path': task['file'],
                        'uploaded_at': datetime.now()
                    }

                    # Cek apakah dokumen sudah ada di koleksi sample
                    existing_sample = sample_collection.find_one(sample_filter)
                    if existing_sample:
                        # Lakukan update jika dokumen sudah ada
                        sample_collection.update_one(
                            sample_filter, {"$set": sample_document})
                    else:
                        # Lakukan insert jika dokumen belum ada
                        sample_collection.insert_one(sample_document)

                    # Tambahkan notifikasi untuk dokumen yang diunggah
                    notification = {
                        'pemberitahuan': f'Dokumen baru telah diunggah untuk proyek {project["project_name"]}: {task["name"]}.',
                        'waktu': datetime.now(),
                        'status': 'belum dibaca'
                    }
                    notifications_collection.update_one(
                        {'user_id': ObjectId(session['user']['_id'])},
                        {'$push': {'notifications': notification}}
                    )

            # Update atau tambahkan statistik untuk tahun saat ini
            current_year = datetime.now().year
            statistik_filter = {'tahun': current_year}
            statistik_update = {'$inc': {'jumlah_project': 1}}

            # Cek apakah sudah ada data statistik untuk tahun ini
            existing_statistik = statistik_collection.find_one(
                statistik_filter)
            if existing_statistik:
                # Lakukan update jika sudah ada
                statistik_collection.update_one(
                    statistik_filter, statistik_update)
            else:
                # Lakukan insert jika belum ada
                statistik_document = {
                    'tahun': current_year,
                    'jumlah_project': 1
                }
                statistik_collection.insert_one(statistik_document)

            # Tambahkan notifikasi untuk perubahan status proyek
            notification = {
                'pemberitahuan': f'Proyek {project["project_name"]} telah ditandai sebagai {new_status}.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.update_one(
                {'user_id': ObjectId(session['user']['_id'])},
                {'$push': {'notifications': notification}}
            )

        return jsonify({"message": f"Project marked as {new_status}", "status_penelitian": new_status}), 200
    else:
        return jsonify({"message": f"Failed to mark project as {new_status}"}), 500

@app.route('/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' in session:
        user_id = session['user_id']
        user_notifications = notifications_collection.find_one(
            {'user_id': ObjectId(user_id)}, {'_id': 0, 'notifications': {'$slice': -5}})
        notifications = user_notifications['notifications'] if user_notifications else [
        ]
        return jsonify({'notifications': notifications})
    return jsonify({'notifications': []})

@app.route('/mark_notifications_as_read', methods=['POST'])
def mark_notifications_as_read():
    if 'user_id' in session:
        user_id = session['user_id']
        notifications_collection.update_one(
            {'user_id': ObjectId(user_id)},
            {'$set': {'notifications.$[elem].status': 'dibaca'}},
            array_filters=[{'elem.status': 'belum dibaca'}]
        )
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 401

@app.route('/edit_task/<project_id>/<task_name>', methods=['POST'])
def edit_task(project_id, task_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return redirect(url_for('login'))

    project = projects_collection.find_one({"_id": ObjectId(project_id)})

    if not project:
        return "Project not found", 404

    new_task_name = request.form['task_name']
    assigned_to = request.form['assigned_to']
    deadline = request.form['deadline']

    # Update the task in the tasks array
    tasks = project['tasks']
    for task in tasks:
        if task['name'] == task_name:
            task['name'] = new_task_name
            task['assigned_to'] = assigned_to

            # Create a notification for task update
            notification = {
                'pemberitahuan': f'Tugas {new_task_name} pada proyek {project["project_name"]} telah diperbarui.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.insert_one(notification)

    # Update the deadline in the schedules array
    schedules = project['schedules']
    for schedule in schedules:
        if schedule['activity_name'] == task_name:
            schedule['activity_name'] = new_task_name
            schedule['assigned_to'] = assigned_to
            schedule['end_date'] = deadline

    projects_collection.update_one({"_id": ObjectId(project_id)}, {
                                   "$set": {"tasks": tasks, "schedules": schedules}})

    flash('Task updated successfully!', 'success')
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/delete_task/<project_id>/<task_name>', methods=['POST'])
def delete_task(project_id, task_name):
    if request.method == 'POST':
        # Hapus task spesifik dari koleksi proyek
        project = projects_collection.find_one({'_id': ObjectId(project_id)})
        if not project:
            flash('Project not found', 'danger')
            return redirect(url_for('project_details', project_id=project_id))

        deleted_task = None
        # Loop through tasks to find and remove task and corresponding schedule
        tasks = project.get('tasks', [])
        schedules = project.get('schedules', [])
        for task in tasks:
            if task['name'] == task_name:
                deleted_task = task
                tasks.remove(task)
                break

        for schedule in schedules:
            if schedule['activity_name'] == task_name:
                schedules.remove(schedule)
                break

        # Update the project document with modified tasks and schedules
        projects_collection.update_one(
            {'_id': ObjectId(project_id)},
            {'$set': {'tasks': tasks, 'schedules': schedules}}
        )

        # Create a notification for task deletion
        if deleted_task:
            notification = {
                'pemberitahuan': f'Tugas {task_name} pada proyek {project["project_name"]} telah dihapus.',
                'waktu': datetime.now(),
                'status': 'belum dibaca'
            }
            notifications_collection.insert_one(notification)

        flash(
            f'Task "{task_name}" and corresponding schedule deleted successfully', 'success')
        return redirect(url_for('project_details', project_id=project_id))

    # Handle case if not a POST request
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_collection.find_one({'email': email})

        if user:
            token = str(ObjectId())
            tokens_collection.insert_one({
                'token': token,
                'user_id': user['_id'],
                'expiry': datetime.utcnow() + timedelta(hours=1)
            })

            reset_link = url_for('reset_password', token=token, _external=True)

            sender = SendSmtpEmailSender(name="YourApp", email="211221002@mhs.stiki.ac.id")
            to = [SendSmtpEmailTo(email=email)]
            html_content = f'<p>Click <a href="{reset_link}">here</a> to reset your password.</p>'
            subject = "Password Reset Request"
            send_smtp_email = SendSmtpEmail(sender=sender, to=to, html_content=html_content, subject=subject)
            try:
                api_instance.send_transac_email(send_smtp_email)
                flash('Password reset link sent to your email.', 'success')
            except Exception as e:
                flash(str(e), 'danger')
        else:
            flash('No account found with that email address.', 'danger')

    return render_template('forgot-password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_data = tokens_collection.find_one({'token': token})
    
    if not token_data or token_data['expiry'] < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form['password']
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        users_collection.update_one(
            {'_id': token_data['user_id']},
            {'$set': {'password': hashed_password}}
        )
        
        tokens_collection.delete_one({'token': token})
        flash('Your password has been updated!', 'success')
        return redirect(url_for('index'))
    
    return render_template('reset-password.html', token=token)

@app.route('/view_sample/<path:file_path>')
def view_sample(file_path):
    # Define the directory where your files are stored
    file_directory = 'static'
    return send_from_directory(file_directory, file_path)

@app.route('/send_chat_file', methods=['POST'])
def send_chat_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files['file']
    project_id = request.form.get('project_id')
    current_user = session.get('user')

    if current_user is None:
        return jsonify({"success": False, "message": "User not logged in"}), 401

    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Get current timestamp in WIB
        tz_wib = pytz.timezone('Asia/Jakarta')
        timestamp = datetime.now(tz_wib)

        messages_collection.update_one(
            {"project_id": project_id},
            {"$push": {"messages": {"text": f"File: {filename}",
                                    "file_path": filename,  # Store filename only
                                    "sender": current_user['name'],
                                    "timestamp": timestamp}}}
        )

        return jsonify({"success": True, "message": f"File {filename} uploaded", "file_path": filename,
                        "sender": current_user['name'], "timestamp": timestamp.isoformat()}), 200

    return jsonify({"success": False, "message": "File upload failed"}), 500

@app.route('/files/<filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, debug=True)