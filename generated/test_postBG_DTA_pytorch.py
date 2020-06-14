import sys
_module = sys.modules[__name__]
del sys
augmentations = _module
misc = _module
consistency_losses = _module
datasets = _module
base = _module
visda = _module
dropout = _module
loggers = _module
losses = _module
main = _module
metrics = _module
models = _module
base = _module
resnet = _module
visda_architectures = _module
options = _module
ramps = _module
trainers = _module
dta_trainer = _module
utils = _module
vat = _module

from _paritybench_helpers import _mock_config
from unittest.mock import mock_open, MagicMock
from torch.autograd import Function
from torch.nn import Module
open = mock_open()
logging = sys = argparse = MagicMock()
ArgumentParser = argparse.ArgumentParser
_global_config = args = argv = cfg = config = params = _mock_config()
argparse.ArgumentParser.return_value.parse_args.return_value = _global_config
sys.argv = _global_config
__version__ = '1.0.0'


from torch import nn as nn


from torch.nn import functional as F


import torch


import torch.nn as nn


import torch.nn.functional as F


import torch.optim as optim


from collections import OrderedDict


from abc import ABC


import math


class AbstractConsistencyLoss(nn.Module):

    def __init__(self, reduction='mean'):
        super().__init__()
        self.reduction = reduction

    def forward(self, logits1, logits2):
        raise NotImplementedError


class EntropyLoss(nn.Module):

    def __init__(self, reduction='mean'):
        super().__init__()
        self.reduction = reduction

    def forward(self, logits):
        p = F.softmax(logits, dim=1)
        elementwise_entropy = -p * F.log_softmax(logits, dim=1)
        if self.reduction == 'none':
            return elementwise_entropy
        sum_entropy = torch.sum(elementwise_entropy, dim=1)
        if self.reduction == 'sum':
            return sum_entropy
        return torch.mean(sum_entropy)


class ClassBalanceLoss(nn.Module):

    def __init__(self, reduction='mean'):
        super().__init__()
        self.reduction = reduction

    def forward(self, logits):
        p = F.softmax(logits, dim=1)
        cls_balance = -torch.mean(torch.log(torch.mean(p, 0) + 1e-06))
        return cls_balance


class KLDivLossWithLogits(AbstractConsistencyLoss):

    def __init__(self, reduction='mean'):
        super().__init__(reduction)
        self.kl_div_loss = nn.KLDivLoss(reduction=reduction)

    def forward(self, logits1, logits2):
        return self.kl_div_loss(F.log_softmax(logits1, dim=1), F.softmax(
            logits2, dim=1))


class LDSLoss(nn.Module):

    def __init__(self, model, xi=1e-06, eps=2.0, ip=1):
        super().__init__()
        self.model = model
        self.vap_generator = VirtualAdversarialPerturbationGenerator(model,
            xi=xi, eps=eps, ip=ip)
        self.kl_div = KLDivLossWithLogits()

    def forward(self, inputs):
        r_adv, logits = self.vap_generator(inputs)
        adv_inputs = inputs + r_adv
        adv_logits = self.model(adv_inputs)
        lds_loss = self.kl_div(adv_logits, logits)
        return lds_loss


class AbstractModel(nn.Module, ABC):

    def state_dict(self, destination=None, prefix='', keep_vars=False):
        state_dict = super().state_dict(destination=destination, prefix=
            prefix, keep_vars=keep_vars)
        new_state_dict = OrderedDict()
        for k, v in state_dict.items():
            name = k.replace('module.', '')
            new_state_dict[name] = v
        return new_state_dict

    def load_state_dict(self, state_dict, strict=True):
        new_state_dict = OrderedDict()
        for k, v in state_dict.items():
            name = k.replace('module.', '')
            new_state_dict[name] = v
        super().load_state_dict(new_state_dict, strict=strict)

    def initialize_parameters(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight.data)

    def stash_grad(self, grad_dict):
        for k, v in self.named_parameters():
            if k in grad_dict:
                grad_dict[k] += v.grad.clone()
            else:
                grad_dict[k] = v.grad.clone()
        self.zero_grad()
        return grad_dict

    def restore_grad(self, grad_dict):
        for k, v in self.named_parameters():
            grad = grad_dict[k] if k in grad_dict else torch.zeros_like(v.grad)
            if v.grad is None:
                v.grad = grad
            else:
                v.grad += grad


def conv3x3(in_planes, out_planes, stride=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
        padding=1, bias=False)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)
        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None, dropout
        =None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
            padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride
        self.dropout = dropout

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)
        out = self.conv3(out)
        out = self.bn3(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)
        if self.dropout is not None:
            out = self.dropout(out)
        return out


import torch
from _paritybench_helpers import _mock_config, _mock_layer, _paritybench_base, _fails_compile

class Test_postBG_DTA_pytorch(_paritybench_base):
    pass
    def test_000(self):
        self._check(BasicBlock(*[], **{'inplanes': 4, 'planes': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_001(self):
        self._check(ClassBalanceLoss(*[], **{}), [torch.rand([4, 4, 4, 4])], {})

    def test_002(self):
        self._check(EntropyLoss(*[], **{}), [torch.rand([4, 4, 4, 4])], {})

    def test_003(self):
        self._check(KLDivLossWithLogits(*[], **{}), [torch.rand([4, 4, 4, 4]), torch.rand([4, 4, 4, 4])], {})

