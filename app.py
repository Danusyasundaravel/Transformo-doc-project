from flask import Flask, request, render_template, send_file
import PyPDF2
import re
import json
import os
from pymongo import MongoClient
from gtts import gTTS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'  # Directory to save uploaded files
app.config['JSON_FOLDER'] = 'json_files'  # Directory to save JSON files
app.config['AUDIO_FOLDER'] = 'audio_files'  # Directory to save audio files

# Ensure upload, json, and audio directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['JSON_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# Setup MongoDB connection
mongo_client = MongoClient("mongodb://localhost:27017/")  # Connect to local MongoDB instance
db = mongo_client['loan_data_db']  # Use or create a database called 'loan_data_db'
collection = db['loan_data']  # Use or create a collection called 'loan_data'

# Function to extract data using regex
def extract_field(pattern, text, default=""):
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else default

# Function to extract data from the PDF
def extract_data_from_pdf(pdf_path):
    pdf_reader = PyPDF2.PdfReader(open(pdf_path, 'rb'))
    extracted_text = ""

    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        extracted_text += page.extract_text()

        # Updated regex patterns based on provided text
    patterns = {
        "address": r"ADDRESS\s*OF\s*THE\s*PLOT\s*\/\s*FLAT\s*\/\s*HOUSE\s*([\w\s,.-]+)",  # Stop before the next section
        "seller_builder": r"NAMES\s*AND\s*ADDRESS\s*OF\s*THE\s*SELLER\s*\/\s*BUILDER\s*.*?(\w+)\s*(?=\n03\.)",  # Capture "Gandhi" before "03."
        "land_area": r"Land Area\s*\(sq\.?\s*ft\.?\)\s*(\d+)",
        "built_up_area": r"Built up Area\s*\(sq\.?\s*ft\.?\)\s*(\d+)",
        "carpet_area": r"Carpet Area\s*\(sq\.?\s*ft\.?\)\s*(\d+)",
        "property_age": r"AGE\s*OF\s*FLAT\s*\/\s*HOUSE\s*IN\s*CASE\s*OF\s*PURCHASE\s*(\d+)",
        "loan_requested": r"Loan requested\s*([\d,]+)",
        "incidental_costs": r"Incident al costs\s*(\d+)" ,
        "cost_of_purchase_construction": r"Cost of purchase\s*\/construction\/repairs\/improvement\/extension\.\s*(\d+)",
        "registration_fees": r"Registration fees\s*(\d+)",
        "stamp_duty":r"Stamp Duty\s*(\d+)",
        "other_costs": r"Any other costs\s*(\d+)",
        "loan_from_relatives": r"Loan from relatives\s*(\d+)",
        "insurance":r"Insurance\s*(\d+)",
        "savings_in_bank": r"Savings in Bank\s*(\d+)",
        "encashable_investments": r"Encashable investments\s*(\d+)",
        "amount_already_spent": r"Amount already spent\s*(\d+)"
        # Capture incidental costs
    }

    
    data = {}
    for field, pattern in patterns.items():
        data[field] = extract_field(pattern, extracted_text)

    return data

def generate_summary(loan_data):
    summary = []
    summary.append(f"Address: {loan_data.get('address', 'N/A')}")
    summary.append(f"Seller/Builder: {loan_data.get('seller_builder', 'N/A')}")

    # Check for area details
    if loan_data.get('land_area') and loan_data.get('built_up_area') and loan_data.get('carpet_area'):
        summary.append(f"Land Area (sq ft): {loan_data['land_area']}")
        summary.append(f"Built Up Area (sq ft): {loan_data['built_up_area']}")
        summary.append(f"Carpet Area (sq ft): {loan_data['carpet_area']}")
    else:
        summary.append("Area details not found.")

    summary.append(f"Property Age: {loan_data.get('property_age', 'N/A')} years")
    summary.append(f"Loan Requested: {loan_data.get('loan_requested', 'N/A')}")
    summary.append(f"Incidental Costs: {loan_data.get('incidental_costs', 'N/A')}")

    return "\n".join(summary)

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            return 'No file part'
        file = request.files['pdf_file']
        if file.filename == '':
            return 'No selected file'
        if file and file.filename.endswith('.pdf'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            loan_data = extract_data_from_pdf(file_path)

            # Debugging: Print extracted loan data to check structure
            print("Extracted Loan Data:", loan_data)

            loan_data_json = json.dumps(loan_data, indent=4)
            json_file_path = os.path.join(app.config['JSON_FOLDER'], file.filename.replace('.pdf', '.json'))
            with open(json_file_path, 'w') as json_file:
                json_file.write(loan_data_json)

            collection.insert_one(loan_data)

            summary_text = generate_summary(loan_data)

            # Generate TTS audio file
            audio_file_path = os.path.join(app.config['AUDIO_FOLDER'], file.filename.replace('.pdf', '.mp3'))
            tts = gTTS(summary_text, lang='en')
            tts.save(audio_file_path)

            return render_template('display.html', loan_data=loan_data, json_file=json_file_path, summary=summary_text, audio_file=audio_file_path)
            

    return render_template('upload.html')

@app.route('/audio/<filename>')
def play_audio(filename):
   return send_file(os.path.join(app.config['AUDIO_FOLDER'], filename))

if __name__ == '__main__':
    app.run(debug=True)
