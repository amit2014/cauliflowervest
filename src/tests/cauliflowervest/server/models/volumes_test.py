#!/usr/bin/env python
#
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""models module tests."""

import datetime
import hashlib


import tests.appenginesdk

from google.appengine.api import users
from google.appengine.ext import db

from google.apputils import app
from google.apputils import basetest

from cauliflowervest.server import settings
from tests.cauliflowervest.server.handlers import test_util
from cauliflowervest.server.models import volumes as models


class FileVaultVolumeTest(basetest.TestCase):
  """Tests FileVaultVolume class."""

  def setUp(self):
    super(FileVaultVolumeTest, self).setUp()
    test_util.SetUpTestbedTestCase(self)

    self.fvv_data = {
        'hdd_serial': 'XX123456',
        'platform_uuid': 'A4E75A65-FC39-441C-BEF5-49D9A3DC6BE0',
        'serial': 'XX123456',
        'passphrase': 'SECRET',
        'volume_uuid': '4E6A59FF-3D85-4B1C-A5D5-70F8B8A9B4A0',
        'created_by': users.User('test@example.com'),
    }
    self.fvv = models.FileVaultVolume(**self.fvv_data)

    # Ensure we use KEY_TYPE_DATASTORE_FILEVAULT and KEY_TYPE_DATASTORE_XSRF for
    # tests.
    self.key_type_default_filevault_save = settings.KEY_TYPE_DEFAULT_FILEVAULT
    self.key_type_default_xsrf_save = settings.KEY_TYPE_DEFAULT_XSRF
    settings.KEY_TYPE_DEFAULT_FILEVAULT = settings.KEY_TYPE_DATASTORE_FILEVAULT
    settings.KEY_TYPE_DEFAULT_XSRF = settings.KEY_TYPE_DATASTORE_XSRF

  def tearDown(self):
    super(FileVaultVolumeTest, self).tearDown()
    test_util.TearDownTestbedTestCase(self)

    settings.KEY_TYPE_DEFAULT_FILEVAULT = self.key_type_default_filevault_save
    settings.KEY_TYPE_DEFAULT_XSRF = self.key_type_default_xsrf_save

  def testSecretProperty(self):
    self.assertEqual(self.fvv.secret, 'SECRET')

  def testSecretChecksum(self):
    self.assertEqual(self.fvv.checksum, hashlib.md5('SECRET').hexdigest())

  def testPutWithoutKeyName(self):
    fvv = models.FileVaultVolume()
    self.assertRaises(models.FileVaultAccessError, fvv.put)

  def testPutWithOnlyCreatedModified(self):
    self.fvv.put()
    self.fvv.created = datetime.datetime.now()
    self.assertRaises(models.FileVaultAccessError, self.fvv.put)

  def testPutWithExistingDataModified(self):
    self.fvv.put()
    num_of_modifications = 1
    for name, prop in self.fvv.properties().iteritems():
      old_value = getattr(self.fvv, name)
      if name == 'active':
        continue
      if isinstance(prop, db.DateTimeProperty):
        continue
      elif isinstance(prop, db.BooleanProperty):
        new_value = not bool(old_value)
      elif isinstance(prop, db.UserProperty):
        new_value = users.User('junk@example.com')
      else:
        new_value = 'JUNK'

      fvv = models.FileVaultVolume(**self.fvv_data)

      setattr(fvv, name, new_value)
      fvv.put()
      num_of_modifications += 1

      volumes = models.FileVaultVolume.all().fetch(999)
      self.assertEqual(num_of_modifications, len(volumes))

  def testPutWithExistingOwnerModified(self):
    self.fvv.put()
    fvv = models.FileVaultVolume(**self.fvv_data)
    fvv.owner = 'new_owner1'
    fvv.put()
    fvv = models.FileVaultVolume(**self.fvv_data)
    fvv.owner = 'new_owner2'
    fvv.put()

  def testPutClone(self):
    self.fvv.put()
    self.assertTrue(self.fvv.active)

    # put() on a Clone of a volume should deactive the old volume.
    clone_volume1 = self.fvv.Clone()
    clone_volume1.owner = 'changed so we will have one different property'
    clone_volume1.put()
    self.fvv = db.get(self.fvv.key())
    self.assertTrue(clone_volume1.active)
    self.assertFalse(self.fvv.active)

    # put() with kw arg "parent=some_volume" should deactivate the parent.
    clone_volume2 = clone_volume1.Clone()
    clone_volume2.owner = 'one different property2'
    clone_volume2.put(parent=clone_volume1)
    clone_volume1 = db.get(clone_volume1.key())
    self.assertTrue(clone_volume2.active)
    self.assertFalse(clone_volume1.active)

  def testPutWithEmptyRequiredProperty(self):
    key_name = u'foo'
    fvv = models.FileVaultVolume(key_name=key_name)

    self.assertRaises(models.FileVaultAccessError, fvv.put)

  def testPutSuccess(self):
    fvv = models.FileVaultVolume()
    for p in models.FileVaultVolume.REQUIRED_PROPERTIES:
      setattr(fvv, p, 'something')

    fvv.put()


class NormalizeHostnameTest(basetest.TestCase):
  """Tests the NormalizeHostname classmethod for all escrow types."""

  def testBitLockerVolume(self):
    self.assertEqual(
        'FOOHOST', models.BitLockerVolume.NormalizeHostname('foohost.dom.com'))

  def testDuplicityKeyPair(self):
    self.assertEqual(
        'foohost.dom.com',
        models.DuplicityKeyPair.NormalizeHostname('FOOHOST.dom.com'))

  def testFileVaultVolume(self):
    self.assertEqual(
        'foohost', models.FileVaultVolume.NormalizeHostname('FOOHOST.dom.com'))

  def testLuksVolume(self):
    self.assertEqual(
        'foohost.dom.com',
        models.LuksVolume.NormalizeHostname('FOOHOST.dom.com'))


def main(unused_argv):
  basetest.main()


if __name__ == '__main__':
  app.run()
