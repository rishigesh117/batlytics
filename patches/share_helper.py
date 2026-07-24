"""
Batlytics — Share & Download Helper
Handles saving PDFs to the device Downloads folder and sharing via Android intents.
"""
import os
import shutil
from kivy.utils import platform


def _ensure_dir(path):
    """Create directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _unique_path(filepath):
    """If file exists, append (2), (3), etc. to make it unique."""
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    counter = 2
    while os.path.exists(f"{base}_({counter}){ext}"):
        counter += 1
    return f"{base}_({counter}){ext}"


def download_pdf(source_path, filename):
    """
    Copies the generated PDF to a public Downloads/Batlytics directory.
    Returns the final path on success, or None on failure.
    """
    if platform == 'android':
        try:
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            downloads_dir = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_DOWNLOADS
            ).getAbsolutePath()

            # Create Batlytics subfolder
            batlytics_dir = os.path.join(downloads_dir, 'Batlytics')
            _ensure_dir(batlytics_dir)

            dest_path = os.path.join(batlytics_dir, filename)
            dest_path = _unique_path(dest_path)

            shutil.copy2(source_path, dest_path)

            # Notify Android media scanner so the file shows up immediately
            try:
                from jnius import autoclass
                MediaScannerConnection = autoclass(
                    'android.media.MediaScannerConnection'
                )
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity
                MediaScannerConnection.scanFile(
                    context, [dest_path], ["application/pdf"], None
                )
            except Exception:
                pass  # Non-critical — file is still saved

            return dest_path
        except Exception as e:
            # Fallback: try saving in app's private storage
            try:
                from kivy.app import App
                app_dir = App.get_running_app().user_data_dir
                batlytics_dir = os.path.join(app_dir, 'Batlytics')
                _ensure_dir(batlytics_dir)
                dest_path = os.path.join(batlytics_dir, filename)
                dest_path = _unique_path(dest_path)
                shutil.copy2(source_path, dest_path)
                return dest_path
            except Exception:
                print("Download error (Android fallback):", e)
                return None
    else:
        # Desktop
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(downloads_dir):
            downloads_dir = os.path.expanduser('~')

        batlytics_dir = os.path.join(downloads_dir, 'Batlytics')
        _ensure_dir(batlytics_dir)

        dest_path = os.path.join(batlytics_dir, filename)
        dest_path = _unique_path(dest_path)
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
            String = autoclass('java.lang.String')
            File = autoclass('java.io.File')

            context = PythonActivity.mActivity

            intent = Intent(Intent.ACTION_SEND)
            intent.setType("application/pdf")

            try:
                # Try FileProvider (Android 7+)
                FileProvider = autoclass(
                    'androidx.core.content.FileProvider'
                )
                authority = (context.getApplicationContext()
                             .getPackageName() + ".fileprovider")
                file_obj = File(file_path)
                uri = FileProvider.getUriForFile(context, authority, file_obj)
                intent.putExtra(
                    Intent.EXTRA_STREAM,
                    cast('android.os.Parcelable', uri)
                )
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            except Exception:
                try:
                    # Fallback: legacy android.support.v4 FileProvider
                    FileProvider = autoclass(
                        'android.support.v4.content.FileProvider'
                    )
                    authority = (context.getApplicationContext()
                                 .getPackageName() + ".fileprovider")
                    file_obj = File(file_path)
                    uri = FileProvider.getUriForFile(
                        context, authority, file_obj
                    )
                    intent.putExtra(
                        Intent.EXTRA_STREAM,
                        cast('android.os.Parcelable', uri)
                    )
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                except Exception:
                    # Final fallback: use direct file URI (older Android)
                    Uri = autoclass('android.net.Uri')
                    uri = Uri.parse("file://" + file_path)
                    intent.putExtra(
                        Intent.EXTRA_STREAM,
                        cast('android.os.Parcelable', uri)
                    )

            chooser = Intent.createChooser(
                intent,
                cast('java.lang.CharSequence', String("Share Scorecard"))
            )
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
