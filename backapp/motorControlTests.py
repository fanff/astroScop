import unittest

from backapp.motorControl import encodeLine, decodeLine


class Test_msgbytes(unittest.TestCase):
    def test0(self):
        ba :bytearray = encodeLine("P", 31.5565656)

        print(ba)
        self.assertEqual(6,len(ba))

    def test1(self):
        res = decodeLine(b'rspd:0.00 mspd:0.00 ts:0.40 err:0.40 cmd:2.56\r\n')

        expected = {"rspd":0.0,
         "mspd":0.0,
         "ts":.40,
         "err":.40,
         "cmd":2.56,
         }

        self.assertDictEqual(expected, res)


