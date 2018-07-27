import base64
import paramiko

import tempfile
from odoo import api, models

import logging
_logger = logging.getLogger(__name__)

try:
    import pysftp
except ImportError:
    _logger.debug('saas_server_backup_ftp requires the python library pysftp which is not found on your installation')


class SaasServerClient(models.Model):
    _inherit = 'saas_server.client'

    @api.model
    def _transport_backup(self, dump_db, filename=None):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        server = ICPSudo.get_param('saas_server.sftp_server', None)
        username = ICPSudo.get_param('saas_server.sftp_username', None)
        password = ICPSudo.get_param('saas_server.sftp_password', None)
        path = ICPSudo.get_param('saas_server.sftp_path', None)
        rsa_key_path = ICPSudo.get_param('saas_server.rsa_key_path', None)
        rsa_key_passphrase=ICPSudo.get_param('saas_server.rsa_key_passphrase'),
        sftp_public_key=ICPSudo.get_param('saas_server.sftp_public_key'),

        params = {
            "host": server,
            "username": username,
        }
        if rsa_key_path:
            params["private_key"] = self.rsa_key_path
            if rsa_key_passphrase:
                params["private_key_pass"] = rsa_key_passphrase
        else:
            params["password"] = password

        cnopts = pysftp.CnOpts()
        if sftp_public_key:
            key = paramiko.RSAKey(data=base64.b64decode(sftp_public_key))
            cnopts.hostkeys.add(self.sftp_server, 'ssh-rsa', key)
        else:
            cnopts.hostkeys = None

        try:
            srv = pysftp.Connection(**params, cnopts=cnopts):

        except (pysftp.CredentialException,
                pysftp.ConnectionException,
                pysftp.SSHException):
            _logger.info("Connection to spft server Failed!", exc_info=True)
            raise

        # set keepalive to prevent socket closed / connection dropped error
        srv._transport.set_keepalive(30)

        try:
            srv.chdir(path)
        except IOError:
            # Create directory and subdirs if they do not exist.
            currentDir = ''
            for dirElement in path.split('/'):
                currentDir += dirElement + '/'
                try:
                    srv.chdir(currentDir)
                except Exception as e:
                    print(('(Part of the) path didn\'t exist. Creating it now at ' + currentDir))
                    # Make directory and then navigate into it
                    srv.mkdir(currentDir, mode=777)
                    srv.chdir(currentDir)

        srv.chdir(path)
        with tempfile.TemporaryFile() as t:
            dump_db(t)
            t.seek(0)
            srv.putfo(t, filename)
        srv.close()

    @api.model
    def schedule_saas_databases_backup(self):
        self.search([('state', '!=', 'deleted')]).backup_database()
