"""Engine-specific preflight must fail for a missing requested backend."""
import contextlib
import io
import unittest
from unittest.mock import patch
from studio import doctor

class DoctorTests(unittest.TestCase):
    def run_doctor(self,args,status):
        with patch.object(doctor,'_run',return_value='1.0'), patch('shutil.which',return_value='/tool'), patch('studio.tts.engine_status',return_value=status), contextlib.redirect_stdout(io.StringIO()):
            return doctor.main(args)

    def test_requested_lfm3_is_required(self):
        self.assertEqual(self.run_doctor(['--engine','lfm3'],{'say':'ok','lfm3':'missing: checkpoint'}),1)

    def test_default_keeps_lfm3_optional(self):
        self.assertEqual(self.run_doctor([],{'say':'ok','lfm3':'missing: checkpoint'}),0)

    def test_requested_engine_does_not_require_unselected_say(self):
        self.assertEqual(self.run_doctor(['--engine','lfm3'],{'say':'missing: say','lfm3':'ok (cached)'}),0)

    def test_unknown_engine_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            self.run_doctor(['--engine','typo'],{'say':'ok'})
        self.assertEqual(cm.exception.code,2)

if __name__=='__main__':unittest.main()
