import sys
_module = sys.modules[__name__]
del sys
extract_features = _module
light_cnn = _module
load_imglist = _module
train = _module

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


import time


import torch


import torch.nn as nn


import torch.nn.parallel


import torch.backends.cudnn as cudnn


import torch.optim


import torch.utils.data


import torch.nn.functional as F


import numpy as np


import math


class mfm(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1,
        padding=1, type=1):
        super(mfm, self).__init__()
        self.out_channels = out_channels
        if type == 1:
            self.filter = nn.Conv2d(in_channels, 2 * out_channels,
                kernel_size=kernel_size, stride=stride, padding=padding)
        else:
            self.filter = nn.Linear(in_channels, 2 * out_channels)

    def forward(self, x):
        x = self.filter(x)
        out = torch.split(x, self.out_channels, 1)
        return torch.max(out[0], out[1])


class group(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size, stride, padding
        ):
        super(group, self).__init__()
        self.conv_a = mfm(in_channels, in_channels, 1, 1, 0)
        self.conv = mfm(in_channels, out_channels, kernel_size, stride, padding
            )

    def forward(self, x):
        x = self.conv_a(x)
        x = self.conv(x)
        return x


class resblock(nn.Module):

    def __init__(self, in_channels, out_channels):
        super(resblock, self).__init__()
        self.conv1 = mfm(in_channels, out_channels, kernel_size=3, stride=1,
            padding=1)
        self.conv2 = mfm(in_channels, out_channels, kernel_size=3, stride=1,
            padding=1)

    def forward(self, x):
        res = x
        out = self.conv1(x)
        out = self.conv2(out)
        out = out + res
        return out


class network_9layers(nn.Module):

    def __init__(self, num_classes=79077):
        super(network_9layers, self).__init__()
        self.features = nn.Sequential(mfm(1, 48, 5, 1, 2), nn.MaxPool2d(
            kernel_size=2, stride=2, ceil_mode=True), group(48, 96, 3, 1, 1
            ), nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True), group
            (96, 192, 3, 1, 1), nn.MaxPool2d(kernel_size=2, stride=2,
            ceil_mode=True), group(192, 128, 3, 1, 1), group(128, 128, 3, 1,
            1), nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True))
        self.fc1 = mfm(8 * 8 * 128, 256, type=0)
        self.fc2 = nn.Linear(256, num_classes)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.fc1(x)
        x = F.dropout(x, training=self.training)
        out = self.fc2(x)
        return out, x


class network_29layers(nn.Module):

    def __init__(self, block, layers, num_classes=79077):
        super(network_29layers, self).__init__()
        self.conv1 = mfm(1, 48, 5, 1, 2)
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True)
        self.block1 = self._make_layer(block, layers[0], 48, 48)
        self.group1 = group(48, 96, 3, 1, 1)
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True)
        self.block2 = self._make_layer(block, layers[1], 96, 96)
        self.group2 = group(96, 192, 3, 1, 1)
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True)
        self.block3 = self._make_layer(block, layers[2], 192, 192)
        self.group3 = group(192, 128, 3, 1, 1)
        self.block4 = self._make_layer(block, layers[3], 128, 128)
        self.group4 = group(128, 128, 3, 1, 1)
        self.pool4 = nn.MaxPool2d(kernel_size=2, stride=2, ceil_mode=True)
        self.fc = mfm(8 * 8 * 128, 256, type=0)
        self.fc2 = nn.Linear(256, num_classes)

    def _make_layer(self, block, num_blocks, in_channels, out_channels):
        layers = []
        for i in range(0, num_blocks):
            layers.append(block(in_channels, out_channels))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.pool1(x)
        x = self.block1(x)
        x = self.group1(x)
        x = self.pool2(x)
        x = self.block2(x)
        x = self.group2(x)
        x = self.pool3(x)
        x = self.block3(x)
        x = self.group3(x)
        x = self.block4(x)
        x = self.group4(x)
        x = self.pool4(x)
        x = x.view(x.size(0), -1)
        fc = self.fc(x)
        fc = F.dropout(fc, training=self.training)
        out = self.fc2(fc)
        return out, fc


class network_29layers_v2(nn.Module):

    def __init__(self, block, layers, num_classes=79077):
        super(network_29layers_v2, self).__init__()
        self.conv1 = mfm(1, 48, 5, 1, 2)
        self.block1 = self._make_layer(block, layers[0], 48, 48)
        self.group1 = group(48, 96, 3, 1, 1)
        self.block2 = self._make_layer(block, layers[1], 96, 96)
        self.group2 = group(96, 192, 3, 1, 1)
        self.block3 = self._make_layer(block, layers[2], 192, 192)
        self.group3 = group(192, 128, 3, 1, 1)
        self.block4 = self._make_layer(block, layers[3], 128, 128)
        self.group4 = group(128, 128, 3, 1, 1)
        self.fc = nn.Linear(8 * 8 * 128, 256)
        self.fc2 = nn.Linear(256, num_classes, bias=False)

    def _make_layer(self, block, num_blocks, in_channels, out_channels):
        layers = []
        for i in range(0, num_blocks):
            layers.append(block(in_channels, out_channels))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = F.max_pool2d(x, 2) + F.avg_pool2d(x, 2)
        x = self.block1(x)
        x = self.group1(x)
        x = F.max_pool2d(x, 2) + F.avg_pool2d(x, 2)
        x = self.block2(x)
        x = self.group2(x)
        x = F.max_pool2d(x, 2) + F.avg_pool2d(x, 2)
        x = self.block3(x)
        x = self.group3(x)
        x = self.block4(x)
        x = self.group4(x)
        x = F.max_pool2d(x, 2) + F.avg_pool2d(x, 2)
        x = x.view(x.size(0), -1)
        fc = self.fc(x)
        x = F.dropout(fc, training=self.training)
        out = self.fc2(x)
        return out, fc


import torch
from _paritybench_helpers import _mock_config, _mock_layer, _paritybench_base, _fails_compile

class Test_AlfredXiangWu_LightCNN(_paritybench_base):
    pass
    def test_000(self):
        self._check(group(*[], **{'in_channels': 4, 'out_channels': 4, 'kernel_size': 4, 'stride': 1, 'padding': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_001(self):
        self._check(mfm(*[], **{'in_channels': 4, 'out_channels': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_002(self):
        self._check(resblock(*[], **{'in_channels': 4, 'out_channels': 4}), [torch.rand([4, 4, 4, 4])], {})

