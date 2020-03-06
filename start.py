from flask import Flask, render_template, request, send_file, redirect, session
import os
import sys
import json
import base64
import piexif
from flask_fontawesome import FontAwesome
from PIL import Image, ImageOps
from io import BytesIO
from werkzeug import secure_filename


# Init flask app and variables
app = Flask(__name__)
fa = FontAwesome(app)
app.secret_key = 'secret_key'
image_types = ['.jpg', '.jpeg']

# Load and prepare config
with open('config.json') as json_data_file:
    data = json.load(json_data_file)
hiddenList   = data["Hidden"]
favList      = data["Favorites"]
password     = data["Password"]
rootDir      = data["rootDir"]

if len(favList) > 0: 
    if(len(favList)>3):
        favList = favList[0:3]
    for idx, val in enumerate(favList):
        favList[idx] = favList[idx].replace('/','>')


@app.route('/login/')
def loginMethod():
    global password
    if(password==''):
        session['login'] = True
    if('login' in session):
        return redirect('/')
    else:
        return render_template('login.html')


@app.route('/login/', methods=['POST'])
def loginPost():
    global password
    text = request.form['text']
    if(text==password):
        session['login'] = True
        return redirect('/')
    else:
        return redirect('/login/')


@app.route('/logout/')
def logoutMethod():
    if('login' in session):
        session.pop('login',None)
    return redirect('/login/')


def image_preview(img_path):
    """ Load image, make preview with corrected exif orientation
    """
    img = Image.open(img_path)
    t_size = 256, 256

    try:
        if "exif" in img.info:
            exif_dict = piexif.load(img.info["exif"])
            if piexif.ImageIFD.Orientation in exif_dict["0th"]:
                orientation = exif_dict["0th"].pop(piexif.ImageIFD.Orientation)
                #exif_bytes = piexif.dump(exif_dict)
                if orientation == 2:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    img = img.rotate(180)
                elif orientation == 4:
                    img = img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 5:
                    img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 6:
                    img = img.rotate(-90, expand=True)
                elif orientation == 7:
                    img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
    except:
        print('exif data problem in', img_path)

    new_image = Image.new(img.mode, t_size,  color=(255,255,255))
    img.thumbnail(t_size, Image.ANTIALIAS) # in-place
    x_offset= (new_image.size[0] - img.size[0]) // 2
    y_offset= (new_image.size[1] - img.size[1]) // 2
    new_image.paste(img, (x_offset, y_offset))
    img = new_image

    # in memory image -> bytes -> base64_string
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_preview = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return img_preview


def hidden(path):
    """ check if one of hidden elements in path
    """
    for item in hiddenList:
        if item != '' and item in path:
            return True
    return False


def changeDirectory(path):
    global rootDir
    pathC = path.split('>')
    if(pathC[0]==""):
        pathC.remove(pathC[0])
    
    myPath = rootDir + '/' + '/'.join(pathC)
    #print(myPath)
    try:
        os.chdir(myPath)
        ans = True
        if(rootDir not in os.getcwd()):
            ans = False
    except:
        ans = False
    
    return ans


def getDirList():
    """ Get list of directories in current directory exclude hidden elements
    """
    dList = list(filter(lambda x: os.path.isdir(x), os.listdir('.')))
    finalList = []
    curDir = os.getcwd()

    for item in dList:
        if(hidden(os.path.join(curDir, item))==False):
            finalList.append(item)

    return(finalList)


def getFileList():
    """ Get list of files in current directory exclude hidden elements
        for image_types make a preview
    """
    dList = list(filter(lambda x: os.path.isfile(x), os.listdir('.')))
    finalList = []
    curDir = os.getcwd()

    for item in dList:
        if(hidden(os.path.join(curDir, item))==False):
            if any(image_type in item.lower() for image_type in image_types):
                preview = image_preview(os.path.join(curDir, item))
                finalList.append((item, preview))
            else:
                finalList.append((item, None))

    return(finalList)


@app.route('/<var>', methods=['GET'])
def filePage(var):
    if('login' not in session):
        return redirect('/login/')
    
    if(changeDirectory(var)==False):
        #Invalid Directory
        print("Directory Doesn't Exist")
        return render_template('404.html',
                                errorCode=300,
                                errorText='Invalid Directory Path',
                                favList=favList)
    try:
        dirList = getDirList()
        fileList = getFileList()
    except:
        return render_template('404.html',
                                errorCode=200,
                                errorText='Permission Denied',
                                favList=favList)
    return render_template('home.html',
                            dirList=dirList,
                            fileList=fileList,
                            currentDir=var,
                            favList=favList)


@app.route('/', methods=['GET'])
def homePage():
    global rootDir
    if('login' not in session):
        return redirect('/login/')
    
    os.chdir(rootDir)
    dirList = getDirList()
    fileList = getFileList()
    return render_template('home.html',
                            dirList=dirList,
                            fileList=fileList,
                            currentDir="",
                            favList=favList)


@app.route('/download/<var>')
def downloadFile(var):
    global rootDir
    if('login' not in session):
        return redirect('/login/')
    
    #os.chdir(rootDir)

    pathC = var.split('>')
    if(pathC[0]==''):
        pathC.remove(pathC[0])
    
    fPath = '/'.join(pathC)
    fPath = rootDir + '/' + fPath
    
    if(hidden(fPath)):
        #FILE HIDDEN
        return render_template('404.html',
                                errorCode=100,
                                errorText='File Hidden',
                                favList=favList)
    fName=pathC[len(pathC)-1]
    #print(fPath)
    try:
        return send_file(fPath, attachment_filename=fName)
    except:
        return render_template('404.html',
                                errorCode=200,
                                errorText='Permission Denied',
                                favList=favList)


@app.errorhandler(404)
def page_not_found(e):
    if('login' not in session):
        return redirect('/login/')
    
    # note that we set the 404 status explicitly
    return render_template('404.html',
                            errorCode=404,
                            errorText='Page Not Found',
                            favList=favList), 404


@app.route('/createfolder/', methods = ['GET', 'POST'])
@app.route('/createfolder/<var>', methods = ['GET', 'POST'])
def createFolder(var=None):
    if('login' not in session):
        return redirect('/login/')
    if request.method == 'POST':
        dir_name = request.form['NewFolderName']
        dir_name = dir_name.replace('/','')

    if var is not None:
        pathC = var.split('>')
    else:
        pathC = ['']
    if(pathC[0]==''):
        pathC.remove(pathC[0])

    fPath = '/'.join(pathC)
    fPath = rootDir + '/' + fPath

    # Make dir
    directory = os.path.join(fPath, dir_name)
    if not os.path.exists(directory):
        os.makedirs(directory)

    if(hidden(fPath)):
        #FILE HIDDEN
        return render_template('404.html',
                                errorCode=100,
                                errorText='File Hidden',
                                favList=favList)

    if var is None:
        return redirect('/')
    return redirect('/'+ var)


@app.route('/upload/', methods = ['GET', 'POST'])
@app.route('/upload/<var>', methods = ['GET', 'POST'])
def uploadFile(var=None):
    if('login' not in session):
        return redirect('/login/')
    
    text = ""
    if request.method == 'POST':
        if var is not None:
            pathC = var.split('>')
        else:
            pathC = ['']
        if(pathC[0]==''):
            pathC.remove(pathC[0])
        
        fPath = '/'.join(pathC)
        fPath = rootDir + '/' + fPath
    
        if(hidden(fPath)):
            #FILE HIDDEN
            return render_template('404.html',
                                    errorCode=100,
                                    errorText='File Hidden',
                                    favList=favList)

        files = request.files.getlist('files[]')
        fileNo = 0
        for file in files:
            fupload = os.path.join(fPath, file.filename)

            if secure_filename(file.filename) and not os.path.exists(fupload):
                try:
                    file.save(fupload)    
                    print(file.filename + ' Uploaded')
                    text = text + file.filename + ' Uploaded<br>'
                    fileNo += 1
                except Exception as e:
                    print(file.filename + ' Failed with Exception '+ str(e))
                    text = text + file.filename + ' Failed with Exception '+ str(e) + '<br>'

                    continue
            else:
                print(file.filename + ' Failed because File Already Exists or File Type Issue')
                text = text + file.filename + ' Failed because File Already Exists or File Type not secure <br>'

    fileNo2 = len(files)-fileNo
    return render_template('uploadsuccess.html',
                            currDir=var,
                            text=text,
                            fileNo=fileNo,
                            fileNo2=fileNo2,
                            favList=favList)


if __name__ == '__main__':
    app.run(host= '0.0.0.0', debug=True)
