# ***************************************************************
# Copyright (c) 2020 Jittor. Authors: Dun Liang <randonlang@gmail.com>. All Rights Reserved.
# This file is subject to the terms and conditions defined in
# file 'LICENSE.txt', which is part of this source code package.
# ***************************************************************
import unittest
import jittor as jt
import numpy as np
from jittor import compile_extern

class TestArray(unittest.TestCase):
    def test_data(self):
        a = jt.array([1,2,3])
        assert (a.data == [1,2,3]).all()
        d = a.data
        a.data[1] = -2
        assert (a.data == [1,-2,3]).all()
        assert (a.fetch_sync()==[1,-2,3]).all()
        li = jt.liveness_info()
        del a
        assert li == jt.liveness_info()
        del d
        assert li != jt.liveness_info()

    def test_set_data(self):
        a = jt.array([1,2,3])
        assert (a.fetch_sync()==[1,2,3]).all()
        a.data = [4,5,6]
        assert (a.fetch_sync()==[4,5,6]).all()
        a.data = jt.array([7,8,9])
        assert (a.fetch_sync()==[7,8,9]).all()

    @unittest.skipIf(not compile_extern.has_cuda, "Cuda not found")
    @jt.flag_scope(use_cuda=1)
    def test_memcopy_overlap(self):
        import time
        from jittor.models import resnet

        im=np.random.rand(100,3,224,224).astype(np.float32)
        net = resnet.Resnet34()
        net.eval()
        # warm up
        x = jt.array(im).stop_grad()

        for i in range(10):
            a = net(x)
            a.sync()
        jt.sync(device_sync=True)

        # pure compute
        time_start=time.time()
        x = jt.array(im).stop_grad()
        for i in range(10):
            a = net(x)
            a.sync()
        jt.sync(device_sync=True)
        t1 = time.time() - time_start

        # warm up
        for i in range(3):
            x = jt.array(im)
            b = net(x)
            b.sync()
        jt.sync(device_sync=True)

        # overlap
        time_start=time.time()
        results = []
        for i in range(10):
            x = jt.array(im)
            b = net(x)
            b.fetch(lambda b: results.append(b))
            # del c
        jt.sync(device_sync=True)
        t2 = time.time() - time_start

        assert t2-t1 < 0.010, (t2, t1, t2-t1)
        assert np.allclose(a.data, b.data)
        assert len(results) == 10
        for v in results:
            assert np.allclose(a.data, v), (v.shape, a.data.shape)
        jt.LOG.v(f"pure compute: {t1}, overlap: {t2}")

    def test_segfault(self):
        a = jt.array([1.0,2.0,3.0])
        b = (jt.maximum(a, 0)).sum() * 2.0
        da = jt.grad(b, a)
        jt.sync_all()
        assert (a.data==[1,2,3]).all()
        assert (da.data==[2,2,2]).all()

    def test_segfault2(self):
        assert (jt.array([1,2,3]).reshape((1,3)).data==[1,2,3]).all()
        if jt.has_cuda:
            with jt.flag_scope(use_cuda=1):
                assert (jt.array([1,2,3]).reshape((1,3)).data==[1,2,3]).all()
    
    @unittest.skipIf(not compile_extern.has_cuda, "Cuda not found")
    def test_array_dual(self):
        with jt.flag_scope(use_cuda=1):
            a = jt.array(np.float32([1,2,3]))
            assert (a.data==[1,2,3]).all()
        
    @unittest.skipIf(not compile_extern.has_cuda, "Cuda not found")
    def test_array_migrate(self):
        with jt.flag_scope(use_cuda=1):
            a = jt.array(np.float32([1,2,3]))
            b = jt.code(a.shape, a.dtype, [a], cpu_src="""
                for (int i=0; i<in0shape0; i++)
                    @out(i) = @in0(i)*@in0(i)*2;
            """)
            assert (b.data==[2,8,18]).all()
        



if __name__ == "__main__":
    unittest.main()