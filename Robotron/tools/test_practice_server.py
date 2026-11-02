import ast
from pathlib import Path
import re
import unittest


class BaseServer:
    def _fail_inference_only(self,reason):
        self.fatal.append(reason)

    @staticmethod
    def _parse_client_handshake(value):
        return bool(value&1),(value>>1)&0x1fff,(value>>14)&3


class PracticeHandshakeTests(unittest.TestCase):
    def test_practice_forces_readonly_mode_but_preserves_slot_and_preview(self):
        source=Path(__file__).with_name('practice_server.py')
        tree=ast.parse(source.read_text())
        node=next(x for x in ast.walk(tree)if isinstance(x,ast.ClassDef)and x.name=='PracticeServer')
        namespace=dict(SocketServer=BaseServer,re=re)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(source),'exec'),namespace)
        server=namespace['PracticeServer']
        for mode in [0,1,2]:
            for slot in [0,29,8191]:
                for preview in [0,1]:
                    raw=(mode<<14)|(slot<<1)|preview
                    self.assertEqual(server._parse_client_handshake(raw),(bool(preview),slot,1))
                    self.assertEqual(server._actor_controls({}), (0.0,0.0,'measurement'))
        with self.assertRaises(ValueError):server._parse_client_handshake(3<<14)
        instance=server();instance.fatal=[]
        for reason in ['Client 0 disconnected: EOF','Client 0 handler ended before intentional shutdown']:
            instance._fail_inference_only(reason)
        self.assertEqual(instance.fatal,[])
        for reason in ['Game journal failed: disk','Client 0 error: nonfinite Q','Socket server failed: bind']:
            instance._fail_inference_only(reason)
        self.assertEqual(len(instance.fatal),3)


if __name__=='__main__':
    unittest.main()
