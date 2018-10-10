import autograd.numpy as np
import autograd.numpy.random as npr
from autograd.scipy.misc import logsumexp
from autograd import grad
from autograd.test_util import check_grads

from ssm.messages import forward_pass, backward_pass, grad_hmm_normalizer
from ssm.primitives import hmm_normalizer
from ssm.models import HMM

from tqdm import trange

def forward_pass_np(log_pi0, log_Ps, log_likes):
    T, K = log_likes.shape
    alphas = []
    alphas.append(log_likes[0] + log_pi0)
    for t in range(T-1):
        anext = logsumexp(alphas[t] + log_Ps[t].T, axis=1)
        anext += log_likes[t+1]
        alphas.append(anext)
    return np.array(alphas)

def hmm_normalizer_np(log_pi0, log_Ps, ll):
    alphas = forward_pass_np(log_pi0, log_Ps, ll)    
    Z = logsumexp(alphas[-1])
    return Z

def make_parameters(T, K):
    log_pi0 = -np.log(K) * np.ones(K)
    As = npr.rand(T-1, K, K)
    As /= As.sum(axis=2, keepdims=True)
    log_Ps = np.log(As)
    ll = npr.randn(T, K)
    return log_pi0, log_Ps, ll

def test_forward_pass(T=1000, K=3):
    log_pi0, log_Ps, ll = make_parameters(T, K)
    a1 = forward_pass_np(log_pi0, log_Ps, ll)
    a2 = np.zeros((T, K))
    forward_pass(-np.log(K) * np.ones(K), log_Ps, ll, a2)
    assert np.allclose(a1, a2)

def test_grad_hmm_normalizer(T=1000, K=3):
    log_pi0, log_Ps, ll = make_parameters(T, K)
    dlog_pi0, dlog_Ps, dll = np.zeros_like(log_pi0), np.zeros_like(log_Ps), np.zeros_like(ll)
    
    alphas = np.zeros((T, K))
    forward_pass(-np.log(K) * np.ones(K), log_Ps, ll, alphas)
    grad_hmm_normalizer(log_Ps, alphas, dlog_pi0, dlog_Ps, dll)

    assert np.allclose(dlog_pi0, grad(hmm_normalizer_np, argnum=0)(log_pi0, log_Ps, ll))
    assert np.allclose(dlog_Ps, grad(hmm_normalizer_np, argnum=1)(log_pi0, log_Ps, ll))
    assert np.allclose(dll, grad(hmm_normalizer_np, argnum=2)(log_pi0, log_Ps, ll))


def test_autograd_primitive(T=1000, K=3):
    # check reverse-mode to second order
    log_pi0, log_Ps, ll = make_parameters(T, K)
    check_grads(hmm_normalizer, argnum=1, modes=['rev'], order=1)(log_pi0, log_Ps, ll)


def test_backward_pass(T=1000, K=5, D=2):
    from pyhsmm.internals.hmm_messages_interface import messages_backwards_log
    
    # Make parameters
    log_pi0 = -np.log(K) * np.ones(K)
    As = npr.rand(K, K)
    As /= As.sum(axis=-1, keepdims=True)
    log_Ps = np.log(np.repeat(As[None, :, :], T-1, axis=0))
    ll = npr.randn(T, K)
    
    # Use pyhsmm to compute
    true_betas = np.zeros((T, K))
    messages_backwards_log(As, ll, true_betas)

    # Use ssm to compute
    test_betas = np.zeros((T, K))
    backward_pass(log_Ps, ll, test_betas)
    
    assert np.allclose(true_betas, test_betas)
