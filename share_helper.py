import os
import shutil
from kivy.utils import platform

def download_pdf(source_path, filename):
    """
    Copies the generated PDF to a public Downloads directory.
    Returns the final path on success, or None on failure.
    """
    if platform == 'android':
        try:
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            downloads_dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()
            dest_path = os.path.join(downloads_dir, filename)
            
            shutil.copy2(source_path, dest_path)
            return dest_path
        except Exception as e:
            print("Download error (Android):", e)
            return None
    else:
        # Desktop
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_dir):
            downloads_dir = os.path.expanduser('~')
        dest_path = os.path.join(downloads_dir, filename)
        shutil.copy2(source_path, dest_path)
        return dest_path

def share_pdf(file_path):
    """
    Triggers the system share dialog for the PDF.
    """
    if platform == 'android':
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            String = autoclass('java.lang.String')
            File = autoclass('java.io.File')
            FileProvider = autoclass('android.support.v4.content.FileProvider')
            
            context = PythonActivity.mActivity
            
            intent = Intent(Intent.ACTION_SEND)
            intent.setType("application/pdf")
            
            try:
                # Try FileProvider (Android 7+)
                authority = context.getApplicationContext().getPackageName() + ".fileprovider"
                file_obj = File(file_path)
                uri = FileProvider.getUriForFile(context, authority, file_obj)
                intent.putExtra(Intent.EXTRA_STREAM, cast('android.os.Parcelable', uri))
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            except Exception:
                # Fallback to standard URI (Android < 7)
                uri = Uri.parse("file://" + file_path)
                intent.putExtra(Intent.EXTRA_STREAM, cast('android.os.Parcelable', uri))
                
            chooser = Intent.createChooser(intent, cast('java.lang.CharSequence', String("Share Scorecard")))
            context.startActivity(chooser)
            return True
        except Exception as e:
            print("Share error (Android):", e)
            return False
    else:
        # Desktop: Just open the folder
        try:
            if os.name == 'nt':
                os.startfile(os.path.dirname(file_path))
            return True
        except Exception:
            return False
