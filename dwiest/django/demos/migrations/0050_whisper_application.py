from django.db import migrations


def add_whisper(apps, schema_editor):
    apps.get_model('demos', 'Application').objects.using(schema_editor.connection.alias).get_or_create(key='whisper')


def remove_whisper(apps, schema_editor):
    apps.get_model('demos', 'Application').objects.using(schema_editor.connection.alias).filter(key='whisper').delete()


class Migration(migrations.Migration):
    dependencies = [('demos', '0049_alter_application_options')]
    operations = [
        migrations.AlterModelOptions(name='application', options={'ordering': ('key',), 'permissions': (('access_whisper', 'Can access Whisper'), ('access_bookmarks', 'Can access Bookmarks'), ('access_invoicer', 'Can access Invoicer'), ('access_journal', 'Can access Journal'), ('access_qrcode', 'Can access QR Code'), ('access_otp', 'Can access Time-Based OTP'), ('access_expenses', 'Can access Expenses'), ('access_inventory', 'Can access Inventory'), ('access_file', 'Can access File Manager'), ('access_news', 'Can access WebSockets'), ('access_selenium', 'Can access Selenium'), ('access_store', 'Can access Store'), ('access_grecaptcha', 'Can access Google reCAPTCHA'), ('access_restapi', 'Can access Legacy REST administration'), ('access_toy_spinning_sticks', 'Can access Spinning Sticks'), ('access_toy_tidal', 'Can access Tidal · Wave Tank'), ('access_toy_plinko', 'Can access Plinko'), ('access_toy_fireworks', 'Can access Pixel Fireworks'), ('access_toy_beam_riders', 'Can access Beam Riders'), ('access_toy_centipede', 'Can access Centipede'), ('access_toy_defender', 'Can access Abduction'), ('access_toy_frogger', 'Can access Frogger'), ('access_toy_galaga', 'Can access Galaga'), ('access_toy_missile_command', 'Can access Missile Command'), ('access_toy_ms_pac_man', 'Can access Ms. Pac-Man'), ('access_toy_rally_x', 'Can access Rally-X'), ('access_toy_space_invaders', 'Can access Space Invaders'), ('access_local_services', 'Can access Local services'), ('access_environment_status', 'Can access Environment status'), ('access_voicemail', 'Can access Voicemail'), ('access_messages', 'Can access Messages'))}),
        migrations.RunPython(add_whisper, remove_whisper),
    ]
