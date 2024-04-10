"""
Code generator script to make the Cython BLAS and LAPACK wrappers
from the files "cython_blas_signatures.txt" and
"cython_lapack_signatures.txt" which contain the signatures for
all the BLAS/LAPACK routines that should be included in the wrappers.

NOTE: Must add scipy/_build_utils to PYTHONPATH for _wrappers_common
"""

import argparse
import os
from _wrappers_common import (C_PREAMBLE, C_TYPES, CPP_GUARD_BEGIN,
                              CPP_GUARD_END, LAPACK_DECLS, NPY_TYPES,
                              WRAPPED_FUNCS, all_newer,
                              get_blas_macro_and_name, read_signatures,
                              write_files)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COMMENT_TEXT = [f"This file was generated by {os.path.basename(__file__)}.\n",
                "Do not edit this file directly.\n"]

blas_pyx_preamble = '''# cython: boundscheck = False
# cython: wraparound = False
# cython: cdivision = True

"""
BLAS Functions for Cython
=========================

Usable from Cython via::

    cimport scipy.linalg.cython_blas

These wrappers do not check for alignment of arrays.
Alignment should be checked before these wrappers are used.

If using ``cdotu``, ``cdotc``, ``zdotu``, ``zdotc``, ``sladiv``, or ``dladiv``,
the environment variable ``CYTHON_CCOMPLEX`` must be 0 during compilation.

Raw function pointers (Fortran-style pointer arguments):

- {}


"""

# Within SciPy, these wrappers can be used via relative or absolute cimport.
# Examples:
# from ..linalg cimport cython_blas
# from scipy.linalg cimport cython_blas
# cimport scipy.linalg.cython_blas as cython_blas
# cimport ..linalg.cython_blas as cython_blas

# Within SciPy, if BLAS functions are needed in C/C++/Fortran,
# these wrappers should not be used.
# The original libraries should be linked directly.

cdef extern from "fortran_defs.h":
    pass

from numpy cimport npy_complex64, npy_complex128

'''

lapack_pyx_preamble = '''"""
LAPACK functions for Cython
===========================

Usable from Cython via::

    cimport scipy.linalg.cython_lapack

This module provides Cython-level wrappers for all primary routines included
in LAPACK 3.4.0 except for ``zcgesv`` since its interface is not consistent
from LAPACK 3.4.0 to 3.6.0. It also provides some of the
fixed-api auxiliary routines.

These wrappers do not check for alignment of arrays.
Alignment should be checked before these wrappers are used.

Raw function pointers (Fortran-style pointer arguments):

- {}


"""

# Within SciPy, these wrappers can be used via relative or absolute cimport.
# Examples:
# from ..linalg cimport cython_lapack
# from scipy.linalg cimport cython_lapack
# cimport scipy.linalg.cython_lapack as cython_lapack
# cimport ..linalg.cython_lapack as cython_lapack

# Within SciPy, if LAPACK functions are needed in C/C++/Fortran,
# these wrappers should not be used.
# The original libraries should be linked directly.

cdef extern from "fortran_defs.h":
    pass

from numpy cimport npy_complex64, npy_complex128

cdef extern from "_lapack_subroutines.h":
    # Function pointer type declarations for
    # gees and gges families of functions.
    ctypedef bint _cselect1(npy_complex64*)
    ctypedef bint _cselect2(npy_complex64*, npy_complex64*)
    ctypedef bint _dselect2(d*, d*)
    ctypedef bint _dselect3(d*, d*, d*)
    ctypedef bint _sselect2(s*, s*)
    ctypedef bint _sselect3(s*, s*, s*)
    ctypedef bint _zselect1(npy_complex128*)
    ctypedef bint _zselect2(npy_complex128*, npy_complex128*)

'''

blas_py_wrappers = """

# Python-accessible wrappers for testing:

cdef inline bint _is_contiguous(double[:,:] a, int axis) noexcept nogil:
    return (a.strides[axis] == sizeof(a[0,0]) or a.shape[axis] == 1)

cpdef float complex _test_cdotc(float complex[:] cx, float complex[:] cy) noexcept nogil:
    cdef:
        int n = cx.shape[0]
        int incx = cx.strides[0] // sizeof(cx[0])
        int incy = cy.strides[0] // sizeof(cy[0])
    return cdotc(&n, &cx[0], &incx, &cy[0], &incy)

cpdef float complex _test_cdotu(float complex[:] cx, float complex[:] cy) noexcept nogil:
    cdef:
        int n = cx.shape[0]
        int incx = cx.strides[0] // sizeof(cx[0])
        int incy = cy.strides[0] // sizeof(cy[0])
    return cdotu(&n, &cx[0], &incx, &cy[0], &incy)

cpdef double _test_dasum(double[:] dx) noexcept nogil:
    cdef:
        int n = dx.shape[0]
        int incx = dx.strides[0] // sizeof(dx[0])
    return dasum(&n, &dx[0], &incx)

cpdef double _test_ddot(double[:] dx, double[:] dy) noexcept nogil:
    cdef:
        int n = dx.shape[0]
        int incx = dx.strides[0] // sizeof(dx[0])
        int incy = dy.strides[0] // sizeof(dy[0])
    return ddot(&n, &dx[0], &incx, &dy[0], &incy)

cpdef int _test_dgemm(double alpha, double[:,:] a, double[:,:] b, double beta,
                double[:,:] c) except -1 nogil:
    cdef:
        char *transa
        char *transb
        int m, n, k, lda, ldb, ldc
        double *a0=&a[0,0]
        double *b0=&b[0,0]
        double *c0=&c[0,0]
    # In the case that c is C contiguous, swap a and b and
    # swap whether or not each of them is transposed.
    # This can be done because a.dot(b) = b.T.dot(a.T).T.
    if _is_contiguous(c, 1):
        if _is_contiguous(a, 1):
            transb = 'n'
            ldb = (&a[1,0]) - a0 if a.shape[0] > 1 else 1
        elif _is_contiguous(a, 0):
            transb = 't'
            ldb = (&a[0,1]) - a0 if a.shape[1] > 1 else 1
        else:
            with gil:
                raise ValueError("Input 'a' is neither C nor Fortran contiguous.")
        if _is_contiguous(b, 1):
            transa = 'n'
            lda = (&b[1,0]) - b0 if b.shape[0] > 1 else 1
        elif _is_contiguous(b, 0):
            transa = 't'
            lda = (&b[0,1]) - b0 if b.shape[1] > 1 else 1
        else:
            with gil:
                raise ValueError("Input 'b' is neither C nor Fortran contiguous.")
        k = b.shape[0]
        if k != a.shape[1]:
            with gil:
                raise ValueError("Shape mismatch in input arrays.")
        m = b.shape[1]
        n = a.shape[0]
        if n != c.shape[0] or m != c.shape[1]:
            with gil:
                raise ValueError("Output array does not have the correct shape.")
        ldc = (&c[1,0]) - c0 if c.shape[0] > 1 else 1
        dgemm(transa, transb, &m, &n, &k, &alpha, b0, &lda, a0,
                   &ldb, &beta, c0, &ldc)
    elif _is_contiguous(c, 0):
        if _is_contiguous(a, 1):
            transa = 't'
            lda = (&a[1,0]) - a0 if a.shape[0] > 1 else 1
        elif _is_contiguous(a, 0):
            transa = 'n'
            lda = (&a[0,1]) - a0 if a.shape[1] > 1 else 1
        else:
            with gil:
                raise ValueError("Input 'a' is neither C nor Fortran contiguous.")
        if _is_contiguous(b, 1):
            transb = 't'
            ldb = (&b[1,0]) - b0 if b.shape[0] > 1 else 1
        elif _is_contiguous(b, 0):
            transb = 'n'
            ldb = (&b[0,1]) - b0 if b.shape[1] > 1 else 1
        else:
            with gil:
                raise ValueError("Input 'b' is neither C nor Fortran contiguous.")
        m = a.shape[0]
        k = a.shape[1]
        if k != b.shape[0]:
            with gil:
                raise ValueError("Shape mismatch in input arrays.")
        n = b.shape[1]
        if m != c.shape[0] or n != c.shape[1]:
            with gil:
                raise ValueError("Output array does not have the correct shape.")
        ldc = (&c[0,1]) - c0 if c.shape[1] > 1 else 1
        dgemm(transa, transb, &m, &n, &k, &alpha, a0, &lda, b0,
                   &ldb, &beta, c0, &ldc)
    else:
        with gil:
            raise ValueError("Input 'c' is neither C nor Fortran contiguous.")
    return 0

cpdef double _test_dnrm2(double[:] x) noexcept nogil:
    cdef:
        int n = x.shape[0]
        int incx = x.strides[0] // sizeof(x[0])
    return dnrm2(&n, &x[0], &incx)

cpdef double _test_dzasum(double complex[:] zx) noexcept nogil:
    cdef:
        int n = zx.shape[0]
        int incx = zx.strides[0] // sizeof(zx[0])
    return dzasum(&n, &zx[0], &incx)

cpdef double _test_dznrm2(double complex[:] x) noexcept nogil:
    cdef:
        int n = x.shape[0]
        int incx = x.strides[0] // sizeof(x[0])
    return dznrm2(&n, &x[0], &incx)

cpdef int _test_icamax(float complex[:] cx) noexcept nogil:
    cdef:
        int n = cx.shape[0]
        int incx = cx.strides[0] // sizeof(cx[0])
    return icamax(&n, &cx[0], &incx)

cpdef int _test_idamax(double[:] dx) noexcept nogil:
    cdef:
        int n = dx.shape[0]
        int incx = dx.strides[0] // sizeof(dx[0])
    return idamax(&n, &dx[0], &incx)

cpdef int _test_isamax(float[:] sx) noexcept nogil:
    cdef:
        int n = sx.shape[0]
        int incx = sx.strides[0] // sizeof(sx[0])
    return isamax(&n, &sx[0], &incx)

cpdef int _test_izamax(double complex[:] zx) noexcept nogil:
    cdef:
        int n = zx.shape[0]
        int incx = zx.strides[0] // sizeof(zx[0])
    return izamax(&n, &zx[0], &incx)

cpdef float _test_sasum(float[:] sx) noexcept nogil:
    cdef:
        int n = sx.shape[0]
        int incx = sx.strides[0] // sizeof(sx[0])
    return sasum(&n, &sx[0], &incx)

cpdef float _test_scasum(float complex[:] cx) noexcept nogil:
    cdef:
        int n = cx.shape[0]
        int incx = cx.strides[0] // sizeof(cx[0])
    return scasum(&n, &cx[0], &incx)

cpdef float _test_scnrm2(float complex[:] x) noexcept nogil:
    cdef:
        int n = x.shape[0]
        int incx = x.strides[0] // sizeof(x[0])
    return scnrm2(&n, &x[0], &incx)

cpdef float _test_sdot(float[:] sx, float[:] sy) noexcept nogil:
    cdef:
        int n = sx.shape[0]
        int incx = sx.strides[0] // sizeof(sx[0])
        int incy = sy.strides[0] // sizeof(sy[0])
    return sdot(&n, &sx[0], &incx, &sy[0], &incy)

cpdef float _test_snrm2(float[:] x) noexcept nogil:
    cdef:
        int n = x.shape[0]
        int incx = x.strides[0] // sizeof(x[0])
    return snrm2(&n, &x[0], &incx)

cpdef double complex _test_zdotc(double complex[:] zx, double complex[:] zy) noexcept nogil:
    cdef:
        int n = zx.shape[0]
        int incx = zx.strides[0] // sizeof(zx[0])
        int incy = zy.strides[0] // sizeof(zy[0])
    return zdotc(&n, &zx[0], &incx, &zy[0], &incy)

cpdef double complex _test_zdotu(double complex[:] zx, double complex[:] zy) noexcept nogil:
    cdef:
        int n = zx.shape[0]
        int incx = zx.strides[0] // sizeof(zx[0])
        int incy = zy.strides[0] // sizeof(zy[0])
    return zdotu(&n, &zx[0], &incx, &zy[0], &incy)
"""

lapack_py_wrappers = """

# Python accessible wrappers for testing:

def _test_dlamch(cmach):
    # This conversion is necessary to handle Python 3 strings.
    cmach_bytes = bytes(cmach)
    # Now that it is a bytes representation, a non-temporary variable
    # must be passed as a part of the function call.
    cdef char* cmach_char = cmach_bytes
    return dlamch(cmach_char)

def _test_slamch(cmach):
    # This conversion is necessary to handle Python 3 strings.
    cmach_bytes = bytes(cmach)
    # Now that it is a bytes representation, a non-temporary variable
    # must be passed as a part of the function call.
    cdef char* cmach_char = cmach_bytes
    return slamch(cmach_char)

cpdef double complex _test_zladiv(double complex zx, double complex zy) noexcept nogil:
    return zladiv(&zx, &zy)

cpdef float complex _test_cladiv(float complex cx, float complex cy) noexcept nogil:
    return cladiv(&cx, &cy)
"""


def arg_casts(argtype):
    """Cast from Cython to Numpy complex pointer types."""
    if argtype in NPY_TYPES.values():
        return f'<{argtype}*>'
    return ''


def generate_decl_pyx(name, return_type, argnames, argtypes, header_name):
    """Create Cython declaration for BLAS/LAPACK function."""
    pyx_input_args = ', '.join([' *'.join(arg) for arg in zip(argtypes, argnames)])
    # By default, nothing is returned
    init_return_var = ''
    return_kw = ''
    return_var = ''
    blas_return_type = 'void'
    # For functions with complex return type, use 'wrp'-suffixed wrappers
    # that take a "return" variable as their first argument and return void
    if name in WRAPPED_FUNCS:
        init_return_var = f'cdef {return_type} out'
        argnames = ['out'] + argnames
        argtypes = [return_type] + argtypes
        return_var = 'return out'
    elif return_type != 'void':
        return_kw = 'return '
        blas_return_type = return_type
    c_argtypes = [NPY_TYPES.get(t, t) for t in argtypes]
    c_proto = ', '.join([' *'.join(arg) for arg in zip(c_argtypes, argnames)])
    pyx_call_args = [arg_casts(t) + n for n, t in zip(argnames, c_argtypes)]
    # Use '&' to get pointer of "return" variable for complex-valued functions
    if name in WRAPPED_FUNCS:
        pyx_call_args[0] = ''.join([arg_casts(c_argtypes[0]), '&', argnames[0]])
    pyx_call_args = ', '.join(pyx_call_args)
    blas_macro, blas_name = get_blas_macro_and_name(name)
    return f"""
cdef extern from "{header_name}":
    {blas_return_type} _fortran_{name} "{blas_macro}({blas_name})"({c_proto}) nogil
cdef {return_type} {name}({pyx_input_args}) noexcept nogil:
    {init_return_var}
    {return_kw}_fortran_{name}({pyx_call_args})
    {return_var}
"""


def generate_file_pyx(sigs, lib_name, header_name):
    """Generate content for pyx file with BLAS/LAPACK declarations and tests."""
    if lib_name == 'BLAS':
        preamble_template = blas_pyx_preamble
        epilog = blas_py_wrappers
    elif lib_name == 'LAPACK':
        preamble_template = lapack_pyx_preamble
        epilog = lapack_py_wrappers
    else:
        raise RuntimeError(f'Unrecognized lib_name: {lib_name}.')
    names = "\n- ".join([sig['name'] for sig in sigs])
    comment = ['# ' + c for c in COMMENT_TEXT]
    preamble = comment + [preamble_template.format(names)]
    decls = [
        generate_decl_pyx(**sig, header_name=header_name)
        for sig in sigs]
    content = preamble + decls + [epilog]
    return ''.join(content)


blas_pxd_preamble = """
# Within scipy, these wrappers can be used via relative or absolute cimport.
# Examples:
# from ..linalg cimport cython_blas
# from scipy.linalg cimport cython_blas
# cimport scipy.linalg.cython_blas as cython_blas
# cimport ..linalg.cython_blas as cython_blas

# Within SciPy, if BLAS functions are needed in C/C++/Fortran,
# these wrappers should not be used.
# The original libraries should be linked directly.

ctypedef float s
ctypedef double d
ctypedef float complex c
ctypedef double complex z

"""

lapack_pxd_preamble = """
# Within SciPy, these wrappers can be used via relative or absolute cimport.
# Examples:
# from ..linalg cimport cython_lapack
# from scipy.linalg cimport cython_lapack
# cimport scipy.linalg.cython_lapack as cython_lapack
# cimport ..linalg.cython_lapack as cython_lapack

# Within SciPy, if LAPACK functions are needed in C/C++/Fortran,
# these wrappers should not be used.
# The original libraries should be linked directly.

ctypedef float s
ctypedef double d
ctypedef float complex c
ctypedef double complex z

# Function pointer type declarations for
# gees and gges families of functions.
ctypedef bint cselect1(c*)
ctypedef bint cselect2(c*, c*)
ctypedef bint dselect2(d*, d*)
ctypedef bint dselect3(d*, d*, d*)
ctypedef bint sselect2(s*, s*)
ctypedef bint sselect3(s*, s*, s*)
ctypedef bint zselect1(z*)
ctypedef bint zselect2(z*, z*)

"""


def generate_decl_pxd(name, return_type, argnames, argtypes):
    """Create Cython header declaration for BLAS/LAPACK function."""
    args = ', '.join([' *'.join(arg) for arg in zip(argtypes, argnames)])
    return f"cdef {return_type} {name}({args}) noexcept nogil\n"


def generate_file_pxd(sigs, lib_name):
    """Create content for Cython header file for generated pyx."""
    if lib_name == 'BLAS':
        preamble = blas_pxd_preamble
    elif lib_name == 'LAPACK':
        preamble = lapack_pxd_preamble
    else:
        raise RuntimeError(f'Unrecognized lib_name: {lib_name}.')
    preamble = ['"""\n', *COMMENT_TEXT, '"""\n', preamble]
    decls = [generate_decl_pxd(**sig)for sig in sigs]
    content = preamble + decls
    return ''.join(content)


def generate_decl_c(name, return_type, argnames, argtypes):
    """Create C header declarations for Cython to import."""
    c_return_type = C_TYPES[return_type]
    c_argtypes = [C_TYPES[t] for t in argtypes]
    # For functions with complex return type, use 'wrp'-suffixed wrappers
    # that take a "return" variable as their first argument and return void
    if name in WRAPPED_FUNCS:
        argnames = ['out'] + argnames
        c_argtypes = [c_return_type] + c_argtypes
        c_return_type = 'void'
    blas_macro, blas_name = get_blas_macro_and_name(name)
    c_args = ', '.join(f'{t} *{n}' for t, n in zip(c_argtypes, argnames))
    return f"{c_return_type} {blas_macro}({blas_name})({c_args});\n"


def generate_file_c(sigs, lib_name):
    """Generate content for C header file for Cython to import."""
    if lib_name == 'BLAS':
        preamble = [C_PREAMBLE]
    elif lib_name == 'LAPACK':
        preamble = [C_PREAMBLE, LAPACK_DECLS]
    else:
        raise RuntimeError(f'Unrecognized lib_name: {lib_name}.')
    preamble = ['/*\n', *COMMENT_TEXT, '*/\n'] + preamble + [CPP_GUARD_BEGIN]
    decls = [generate_decl_c(**sig) for sig in sigs]
    content = preamble + decls + [CPP_GUARD_END]
    return ''.join(content)


def make_all(outdir,
             blas_signature_file="cython_blas_signatures.txt",
             lapack_signature_file="cython_lapack_signatures.txt",
             blas_name="cython_blas",
             lapack_name="cython_lapack",
             blas_header_name="_blas_subroutines.h",
             lapack_header_name="_lapack_subroutines.h"):
    src_files = (os.path.abspath(__file__),
                 blas_signature_file,
                 lapack_signature_file)
    dst_files = (blas_name + '.pyx',
                 blas_name + '.pxd',
                 blas_header_name,
                 lapack_name + '.pyx',
                 lapack_name + '.pxd',
                 lapack_header_name)
    dst_files = [os.path.join(outdir, f) for f in dst_files]
    os.chdir(BASE_DIR)
    if all_newer(dst_files, src_files):
        print("scipy/linalg/_generate_pyx.py: all files up-to-date")
        return
    with open(blas_signature_file) as f:
        blas_sigs = f.readlines()
    blas_sigs = read_signatures(blas_sigs)
    with open(lapack_signature_file) as f:
        lapack_sigs = f.readlines()
    lapack_sigs = read_signatures(lapack_sigs)
    to_write = {
        dst_files[0]: generate_file_pyx(
            blas_sigs, 'BLAS', blas_header_name),
        dst_files[1]: generate_file_pxd(blas_sigs, 'BLAS'),
        dst_files[2]: generate_file_c(blas_sigs, 'BLAS'),
        dst_files[3]: generate_file_pyx(
            lapack_sigs, 'LAPACK', lapack_header_name),
        dst_files[4]: generate_file_pxd(lapack_sigs, 'LAPACK'),
        dst_files[5]: generate_file_c(lapack_sigs, 'LAPACK')
    }
    write_files(to_write)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--outdir", type=str,
                        help="Path to the output directory")
    args = parser.parse_args()

    if not args.outdir:
        raise ValueError("Missing `--outdir` argument to _generate_pyx.py")
    else:
        outdir_abs = os.path.join(os.getcwd(), args.outdir)

    make_all(outdir_abs)
