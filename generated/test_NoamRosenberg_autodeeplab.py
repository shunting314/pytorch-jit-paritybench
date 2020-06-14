import sys
_module = sys.modules[__name__]
del sys
auto_deeplab = _module
cell_level_search = _module
decode_args = _module
evaluate_args = _module
re_train_autodeeplab = _module
re_train_deeplab_v3plus = _module
retrain_config = _module
search_args = _module
dataloaders = _module
custom_transforms = _module
dataloader_utils = _module
datasets = _module
cityscapes = _module
coco = _module
combine_dbs = _module
kd = _module
pascal = _module
sbd = _module
decode_autodeeplab = _module
decoding_formulas = _module
deeplab_resnet = _module
deeplab_xception = _module
evaluate = _module
evaluate_distributed = _module
genotypes = _module
modeling = _module
aspp = _module
backbone = _module
drn = _module
mobilenet = _module
resnet = _module
xception = _module
decoder = _module
deeplab = _module
modules = _module
bn = _module
functions = _module
misc = _module
sync_batchnorm = _module
batchnorm = _module
comm = _module
replicate = _module
unittest = _module
operations = _module
aspp = _module
build_autodeeplab = _module
decoder = _module
new_model = _module
summaries = _module
test = _module
train = _module
train_autodeeplab = _module
train_distributed = _module
calculate_weights = _module
copy_state_dict = _module
logger = _module
loss = _module
lr_scheduler = _module
metrics = _module
optimizer_distributed = _module
preprocess = _module
saver = _module
step_lr_scheduler = _module
utils = _module

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


import torch.nn as nn


import torch.nn.functional as F


import math


import torch


import random


import numpy as np


from numpy import int64 as int64


import torch.utils.model_zoo as model_zoo


import torch.backends.cudnn


from torch.utils.data.dataloader import DataLoader


from torch.utils.data import DataLoader


import torch.distributed as dist


import logging


import warnings


import torch.nn.functional as functional


import collections


from torch.nn.modules.batchnorm import _BatchNorm


from torch.nn.parallel._functions import ReduceAddCoalesced


from torch.nn.parallel._functions import Broadcast


import functools


from torch.nn.parallel.data_parallel import DataParallel


import torch.utils.data


import torch.optim as optim


from collections import OrderedDict


import time


import torch.backends


def network_layer_to_space(net_arch):
    for i, layer in enumerate(net_arch):
        if i == 0:
            space = np.zeros((1, 4, 3))
            space[0][layer][0] = 1
            prev = layer
        else:
            if layer == prev + 1:
                sample = 0
            elif layer == prev:
                sample = 1
            elif layer == prev - 1:
                sample = 2
            space1 = np.zeros((1, 4, 3))
            space1[0][layer][sample] = 1
            space = np.concatenate([space, space1], axis=0)
            prev = layer
    """
        return:
        network_space[layer][level][sample]:
        layer: 0 - 12
        level: sample_level {0: 1, 1: 2, 2: 4, 3: 8}
        sample: 0: down 1: None 2: Up
    """
    return space


class Decoder(object):

    def __init__(self, alphas, betas, steps):
        self._betas = betas
        self._alphas = alphas
        self._steps = steps
        self._num_layers = self._betas.shape[0]
        self.network_space = torch.zeros(12, 4, 3)
        for layer in range(self._num_layers):
            if layer == 0:
                self.network_space[layer][0][1:] = F.softmax(self._betas[
                    layer][0][1:], dim=-1) * (2 / 3)
            elif layer == 1:
                self.network_space[layer][0][1:] = F.softmax(self._betas[
                    layer][0][1:], dim=-1) * (2 / 3)
                self.network_space[layer][1] = F.softmax(self._betas[layer]
                    [1], dim=-1)
            elif layer == 2:
                self.network_space[layer][0][1:] = F.softmax(self._betas[
                    layer][0][1:], dim=-1) * (2 / 3)
                self.network_space[layer][1] = F.softmax(self._betas[layer]
                    [1], dim=-1)
                self.network_space[layer][2] = F.softmax(self._betas[layer]
                    [2], dim=-1)
            else:
                self.network_space[layer][0][1:] = F.softmax(self._betas[
                    layer][0][1:], dim=-1) * (2 / 3)
                self.network_space[layer][1] = F.softmax(self._betas[layer]
                    [1], dim=-1)
                self.network_space[layer][2] = F.softmax(self._betas[layer]
                    [2], dim=-1)
                self.network_space[layer][3][:2] = F.softmax(self._betas[
                    layer][3][:2], dim=-1) * (2 / 3)

    def viterbi_decode(self):
        prob_space = np.zeros(self.network_space.shape[:2])
        path_space = np.zeros(self.network_space.shape[:2]).astype('int8')
        for layer in range(self.network_space.shape[0]):
            if layer == 0:
                prob_space[layer][0] = self.network_space[layer][0][1]
                prob_space[layer][1] = self.network_space[layer][0][2]
                path_space[layer][0] = 0
                path_space[layer][1] = -1
            else:
                for sample in range(self.network_space.shape[1]):
                    if layer - sample < -1:
                        continue
                    local_prob = []
                    for rate in range(self.network_space.shape[2]):
                        if (sample == 0 and rate == 2 or sample == 3 and 
                            rate == 0):
                            continue
                        else:
                            local_prob.append(prob_space[layer - 1][sample +
                                1 - rate] * self.network_space[layer][
                                sample + 1 - rate][rate])
                    prob_space[layer][sample] = np.max(local_prob, axis=0)
                    rate = np.argmax(local_prob, axis=0)
                    path = 1 - rate if sample != 3 else -rate
                    path_space[layer][sample] = path
        output_sample = prob_space[(-1), :].argmax(axis=-1)
        actual_path = np.zeros(12).astype('uint8')
        actual_path[-1] = output_sample
        for i in range(1, self._num_layers):
            actual_path[-i - 1] = actual_path[-i] + path_space[self.
                _num_layers - i, actual_path[-i]]
        return actual_path, network_layer_to_space(actual_path)

    def dfs_decode(self):
        best_result = []
        max_prop = 0

        def _parse(weight_network, layer, curr_value, curr_result, last):
            nonlocal best_result
            nonlocal max_prop
            if layer == self._num_layers:
                if max_prop < curr_value:
                    best_result = curr_result[:]
                    max_prop = curr_value
                return
            if layer == 0:
                print('begin0')
                num = 0
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    print('end0-1')
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
            elif layer == 1:
                print('begin1')
                num = 0
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    print('end1-1')
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                num = 1
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][2]
                    curr_result.append([num, 2])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][2]
                    curr_result.pop()
            elif layer == 2:
                print('begin2')
                num = 0
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    print('end2-1')
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                num = 1
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][2]
                    curr_result.append([num, 2])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][2]
                    curr_result.pop()
                num = 2
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][2]
                    curr_result.append([num, 2])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 3)
                    curr_value = curr_value / weight_network[layer][num][2]
                    curr_result.pop()
            else:
                num = 0
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                num = 1
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 0)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][2]
                    curr_result.append([num, 2])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][2]
                    curr_result.pop()
                num = 2
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 1)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][2]
                    curr_result.append([num, 2])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 3)
                    curr_value = curr_value / weight_network[layer][num][2]
                    curr_result.pop()
                num = 3
                if last == num:
                    curr_value = curr_value * weight_network[layer][num][0]
                    curr_result.append([num, 0])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 2)
                    curr_value = curr_value / weight_network[layer][num][0]
                    curr_result.pop()
                    curr_value = curr_value * weight_network[layer][num][1]
                    curr_result.append([num, 1])
                    _parse(weight_network, layer + 1, curr_value,
                        curr_result, 3)
                    curr_value = curr_value / weight_network[layer][num][1]
                    curr_result.pop()
        network_weight = F.softmax(self.last_betas_network, dim=-1) * 5
        network_weight = network_weight.data.cpu().numpy()
        _parse(network_weight, 0, 1, [], 0)
        print(max_prop)
        return best_result

    def genotype_decode(self):

        def _parse(alphas, steps):
            gene = []
            start = 0
            n = 2
            for i in range(steps):
                end = start + n
                edges = sorted(range(start, end), key=lambda x: -np.max(
                    alphas[(x), 1:]))
                top2edges = edges[:2]
                for j in top2edges:
                    best_op_index = np.argmax(alphas[j])
                    gene.append([j, best_op_index])
                start = end
                n += 1
            return np.array(gene)
        normalized_alphas = F.softmax(self._alphas, dim=-1).data.cpu().numpy()
        gene_cell = _parse(normalized_alphas, self._steps)
        return gene_cell


PRIMITIVES = ['none', 'max_pool_3x3', 'avg_pool_3x3', 'skip_connect',
    'sep_conv_3x3', 'sep_conv_5x5', 'dil_conv_3x3', 'dil_conv_5x5']


OPS = {'none': lambda C, stride, affine, use_ABN: Zero(stride),
    'avg_pool_3x3': lambda C, stride, affine, use_ABN: nn.AvgPool2d(3,
    stride=stride, padding=1, count_include_pad=False), 'max_pool_3x3': lambda
    C, stride, affine, use_ABN: nn.MaxPool2d(3, stride=stride, padding=1),
    'skip_connect': lambda C, stride, affine, use_ABN: Identity() if stride ==
    1 else FactorizedReduce(C, C, affine=affine), 'sep_conv_3x3': lambda C,
    stride, affine, use_ABN: SepConv(C, C, 3, stride, 1, affine=affine),
    'sep_conv_5x5': lambda C, stride, affine, use_ABN: SepConv(C, C, 5,
    stride, 2, affine=affine), 'dil_conv_3x3': lambda C, stride, affine,
    use_ABN: DilConv(C, C, 3, stride, 2, 2, affine=affine, use_ABN=use_ABN),
    'dil_conv_5x5': lambda C, stride, affine, use_ABN: DilConv(C, C, 5,
    stride, 4, 2, affine=affine, use_ABN=use_ABN)}


class MixedOp(nn.Module):

    def __init__(self, C, stride):
        super(MixedOp, self).__init__()
        self._ops = nn.ModuleList()
        for primitive in PRIMITIVES:
            op = OPS[primitive](C, stride, False, False)
            if 'pool' in primitive:
                op = nn.Sequential(op, nn.BatchNorm2d(C, affine=False))
            self._ops.append(op)

    def forward(self, x, weights):
        return sum(w * op(x) for w, op in zip(weights, self._ops))


class Cell(nn.Module):

    def __init__(self, steps, block_multiplier, prev_prev_fmultiplier,
        prev_fmultiplier_down, prev_fmultiplier_same, prev_fmultiplier_up,
        filter_multiplier):
        super(Cell, self).__init__()
        self.C_in = block_multiplier * filter_multiplier
        self.C_out = filter_multiplier
        self.C_prev_prev = int(prev_prev_fmultiplier * block_multiplier)
        self._prev_fmultiplier_same = prev_fmultiplier_same
        if prev_fmultiplier_down is not None:
            self.C_prev_down = int(prev_fmultiplier_down * block_multiplier)
            self.preprocess_down = ReLUConvBN(self.C_prev_down, self.C_out,
                1, 1, 0, affine=False)
        if prev_fmultiplier_same is not None:
            self.C_prev_same = int(prev_fmultiplier_same * block_multiplier)
            self.preprocess_same = ReLUConvBN(self.C_prev_same, self.C_out,
                1, 1, 0, affine=False)
        if prev_fmultiplier_up is not None:
            self.C_prev_up = int(prev_fmultiplier_up * block_multiplier)
            self.preprocess_up = ReLUConvBN(self.C_prev_up, self.C_out, 1, 
                1, 0, affine=False)
        if prev_prev_fmultiplier != -1:
            self.pre_preprocess = ReLUConvBN(self.C_prev_prev, self.C_out, 
                1, 1, 0, affine=False)
        self._steps = steps
        self.block_multiplier = block_multiplier
        self._ops = nn.ModuleList()
        for i in range(self._steps):
            for j in range(2 + i):
                stride = 1
                if prev_prev_fmultiplier == -1 and j == 0:
                    op = None
                else:
                    op = MixedOp(self.C_out, stride)
                self._ops.append(op)
        self._initialize_weights()

    def scale_dimension(self, dim, scale):
        assert isinstance(dim, int)
        return int((float(dim) - 1.0) * scale + 1.0) if dim % 2 else int(
            dim * scale)

    def prev_feature_resize(self, prev_feature, mode):
        if mode == 'down':
            feature_size_h = self.scale_dimension(prev_feature.shape[2], 0.5)
            feature_size_w = self.scale_dimension(prev_feature.shape[3], 0.5)
        elif mode == 'up':
            feature_size_h = self.scale_dimension(prev_feature.shape[2], 2)
            feature_size_w = self.scale_dimension(prev_feature.shape[3], 2)
        return F.interpolate(prev_feature, (feature_size_h, feature_size_w),
            mode='bilinear', align_corners=True)

    def forward(self, s0, s1_down, s1_same, s1_up, n_alphas):
        if s1_down is not None:
            s1_down = self.prev_feature_resize(s1_down, 'down')
            s1_down = self.preprocess_down(s1_down)
            size_h, size_w = s1_down.shape[2], s1_down.shape[3]
        if s1_same is not None:
            s1_same = self.preprocess_same(s1_same)
            size_h, size_w = s1_same.shape[2], s1_same.shape[3]
        if s1_up is not None:
            s1_up = self.prev_feature_resize(s1_up, 'up')
            s1_up = self.preprocess_up(s1_up)
            size_h, size_w = s1_up.shape[2], s1_up.shape[3]
        all_states = []
        if s0 is not None:
            s0 = F.interpolate(s0, (size_h, size_w), mode='bilinear',
                align_corners=True) if s0.shape[2] != size_h or s0.shape[3
                ] != size_w else s0
            s0 = self.pre_preprocess(s0) if s0.shape[1] != self.C_out else s0
            if s1_down is not None:
                states_down = [s0, s1_down]
                all_states.append(states_down)
            if s1_same is not None:
                states_same = [s0, s1_same]
                all_states.append(states_same)
            if s1_up is not None:
                states_up = [s0, s1_up]
                all_states.append(states_up)
        else:
            if s1_down is not None:
                states_down = [0, s1_down]
                all_states.append(states_down)
            if s1_same is not None:
                states_same = [0, s1_same]
                all_states.append(states_same)
            if s1_up is not None:
                states_up = [0, s1_up]
                all_states.append(states_up)
        final_concates = []
        for states in all_states:
            offset = 0
            for i in range(self._steps):
                new_states = []
                for j, h in enumerate(states):
                    branch_index = offset + j
                    if self._ops[branch_index] is None:
                        continue
                    new_state = self._ops[branch_index](h, n_alphas[
                        branch_index])
                    new_states.append(new_state)
                s = sum(new_states)
                offset += len(states)
                states.append(s)
            concat_feature = torch.cat(states[-self.block_multiplier:], dim=1)
            final_concates.append(concat_feature)
        return final_concates

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class ResNet(nn.Module):

    def __init__(self, nInputChannels, block, layers, os=16, pretrained=False):
        self.inplanes = 64
        super(ResNet, self).__init__()
        if os == 16:
            strides = [1, 2, 2, 1]
            dilations = [1, 1, 1, 2]
            blocks = [1, 2, 4]
        elif os == 8:
            strides = [1, 2, 1, 1]
            dilations = [1, 1, 2, 2]
            blocks = [1, 2, 1]
        else:
            raise NotImplementedError
        self.conv1 = nn.Conv2d(nInputChannels, 64, kernel_size=7, stride=2,
            padding=3, bias=False)
        self.bn1 = BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0], stride=strides
            [0], dilation=dilations[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=
            strides[1], dilation=dilations[1])
        self.layer3 = self._make_layer(block, 256, layers[2], stride=
            strides[2], dilation=dilations[2])
        self.layer4 = self._make_MG_unit(block, 512, blocks=blocks, stride=
            strides[3], dilation=dilations[3])
        self._init_weight()
        if pretrained:
            self._load_pretrained_model()

    def _make_layer(self, block, planes, blocks, stride=1, dilation=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm2d(planes * block.expansion))
        layers = []
        layers.append(block(self.inplanes, planes, stride, dilation,
            downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return nn.Sequential(*layers)

    def _make_MG_unit(self, block, planes, blocks=[1, 2, 4], stride=1,
        dilation=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm2d(planes * block.expansion))
        layers = []
        layers.append(block(self.inplanes, planes, stride, dilation=blocks[
            0] * dilation, downsample=downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, len(blocks)):
            layers.append(block(self.inplanes, planes, stride=1, dilation=
                blocks[i] * dilation))
        return nn.Sequential(*layers)

    def forward(self, input):
        x = self.conv1(input)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        low_level_feat = x
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x, low_level_feat

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _load_pretrained_model(self):
        pretrain_dict = model_zoo.load_url(
            'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth')
        model_dict = {}
        state_dict = self.state_dict()
        for k, v in pretrain_dict.items():
            if k in state_dict:
                model_dict[k] = v
        state_dict.update(model_dict)
        self.load_state_dict(state_dict)


class ASPP_module(nn.Module):

    def __init__(self, inplanes, planes, dilation):
        super(ASPP_module, self).__init__()
        if dilation == 1:
            kernel_size = 1
            padding = 0
        else:
            kernel_size = 3
            padding = dilation
        self.atrous_convolution = nn.Conv2d(inplanes, planes, kernel_size=
            kernel_size, stride=1, padding=padding, dilation=dilation, bias
            =False)
        self.bn = BatchNorm2d(planes)
        self.relu = nn.ReLU()
        self._init_weight()

    def forward(self, x):
        x = self.atrous_convolution(x)
        x = self.bn(x)
        return self.relu(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


def ResNet101(output_stride, BatchNorm, pretrained=True):
    """Constructs a ResNet-101 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 23, 3], output_stride, BatchNorm,
        pretrained=pretrained)
    return model


class DeepLabv3_plus(nn.Module):

    def __init__(self, nInputChannels=3, n_classes=21, os=16, pretrained=
        False, freeze_bn=False, _print=True):
        if _print:
            None
            None
            None
            None
            None
        super(DeepLabv3_plus, self).__init__()
        self.resnet_features = ResNet101(nInputChannels, os, pretrained=
            pretrained)
        if os == 16:
            dilations = [1, 6, 12, 18]
        elif os == 8:
            dilations = [1, 12, 24, 36]
        else:
            raise NotImplementedError
        self.aspp1 = ASPP_module(2048, 256, dilation=dilations[0])
        self.aspp2 = ASPP_module(2048, 256, dilation=dilations[1])
        self.aspp3 = ASPP_module(2048, 256, dilation=dilations[2])
        self.aspp4 = ASPP_module(2048, 256, dilation=dilations[3])
        self.relu = nn.ReLU()
        self.global_avg_pool = nn.Sequential(nn.AdaptiveAvgPool2d((1, 1)),
            nn.Conv2d(2048, 256, 1, stride=1, bias=False), BatchNorm2d(256),
            nn.ReLU())
        self.conv1 = nn.Conv2d(1280, 256, 1, bias=False)
        self.bn1 = BatchNorm2d(256)
        self.conv2 = nn.Conv2d(256, 48, 1, bias=False)
        self.bn2 = BatchNorm2d(48)
        self.last_conv = nn.Sequential(nn.Conv2d(304, 256, kernel_size=3,
            stride=1, padding=1, bias=False), BatchNorm2d(256), nn.ReLU(),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1, bias=
            False), BatchNorm2d(256), nn.ReLU(), nn.Conv2d(256, n_classes,
            kernel_size=1, stride=1))
        if freeze_bn:
            self._freeze_bn()

    def forward(self, input):
        x, low_level_features = self.resnet_features(input)
        x1 = self.aspp1(x)
        x2 = self.aspp2(x)
        x3 = self.aspp3(x)
        x4 = self.aspp4(x)
        x5 = self.global_avg_pool(x)
        x5 = F.upsample(x5, size=x4.size()[2:], mode='bilinear',
            align_corners=True)
        x = torch.cat((x1, x2, x3, x4, x5), dim=1)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = F.upsample(x, size=(int(math.ceil(input.size()[-2] / 4)), int(
            math.ceil(input.size()[-1] / 4))), mode='bilinear',
            align_corners=True)
        low_level_features = self.conv2(low_level_features)
        low_level_features = self.bn2(low_level_features)
        low_level_features = self.relu(low_level_features)
        x = torch.cat((x, low_level_features), dim=1)
        x = self.last_conv(x)
        x = F.interpolate(x, size=input.size()[2:], mode='bilinear',
            align_corners=True)
        return x

    def _freeze_bn(self):
        for m in self.modules():
            if isinstance(m, BatchNorm2d):
                m.eval()

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class SeparableConv2d(nn.Module):

    def __init__(self, inplanes, planes, kernel_size=3, stride=1, padding=0,
        dilation=1, bias=False):
        super(SeparableConv2d, self)._init_()
        self.conv1 = nn.Conv2d(inplanes, inplanes, kernel_size, stride,
            padding, dilation, groups=inplanes, bias=bias)
        self.pointwise = nn.Conv2d(inplanes, planes, 1, 1, 0, 1, 1, bias=bias)

    def forward(self, x):
        x = self.conv1(x)
        x = self.pointwise(x)
        return x


def fixed_padding(inputs, kernel_size, dilation):
    kernel_size_effective = kernel_size + (kernel_size - 1) * (dilation - 1)
    pad_total = kernel_size_effective - 1
    pad_beg = pad_total // 2
    pad_end = pad_total - pad_beg
    padded_inputs = F.pad(inputs, (pad_beg, pad_end, pad_beg, pad_end))
    return padded_inputs


class SeparableConv2d_same(nn.Module):

    def __init__(self, inplanes, planes, kernel_size=3, stride=1, dilation=
        1, bias=False):
        super(SeparableConv2d_same, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, inplanes, kernel_size, stride, 0,
            dilation, groups=inplanes, bias=bias)
        self.pointwise = nn.Conv2d(inplanes, planes, 1, 1, 0, 1, 1, bias=bias)

    def forward(self, x):
        x = fixed_padding(x, self.conv1.kernel_size[0], dilation=self.conv1
            .dilation[0])
        x = self.conv1(x)
        x = self.pointwise(x)
        return x


class Block(nn.Module):

    def __init__(self, inplanes, planes, reps, stride=1, dilation=1,
        start_with_relu=True, grow_first=True, is_last=False):
        super(Block, self).__init__()
        if planes != inplanes or stride != 1:
            self.skip = nn.Conv2d(inplanes, planes, 1, stride=stride, bias=
                False)
            self.skipbn = BatchNorm2d(planes)
        else:
            self.skip = None
        self.relu = nn.ReLU(inplace=True)
        rep = []
        filters = inplanes
        if grow_first:
            rep.append(self.relu)
            rep.append(SeparableConv2d_same(inplanes, planes, 3, stride=1,
                dilation=dilation))
            rep.append(BatchNorm2d(planes))
            filters = planes
        for i in range(reps - 1):
            rep.append(self.relu)
            rep.append(SeparableConv2d_same(filters, filters, 3, stride=1,
                dilation=dilation))
            rep.append(BatchNorm2d(filters))
        if not grow_first:
            rep.append(self.relu)
            rep.append(SeparableConv2d_same(inplanes, planes, 3, stride=1,
                dilation=dilation))
            rep.append(BatchNorm2d(planes))
        if not start_with_relu:
            rep = rep[1:]
        if stride != 1:
            rep.append(SeparableConv2d_same(planes, planes, 3, stride=2))
        if stride == 1 and is_last:
            rep.append(SeparableConv2d_same(planes, planes, 3, stride=1))
        self.rep = nn.Sequential(*rep)

    def forward(self, inp):
        x = self.rep(inp)
        if self.skip is not None:
            skip = self.skip(inp)
            skip = self.skipbn(skip)
        else:
            skip = inp
        x += skip
        return x


class Xception(nn.Module):
    """
    Modified Alighed Xception
    """

    def __init__(self, inplanes=3, os=16, pretrained=False):
        super(Xception, self).__init__()
        if os == 16:
            entry_block3_stride = 2
            middle_block_dilation = 1
            exit_block_dilations = 1, 2
        elif os == 8:
            entry_block3_stride = 1
            middle_block_dilation = 2
            exit_block_dilations = 2, 4
        else:
            raise NotImplementedError
        self.conv1 = nn.Conv2d(inplanes, 32, 3, stride=2, padding=1, bias=False
            )
        self.bn1 = BatchNorm2d(32)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(32, 64, 3, stride=1, padding=1, bias=False)
        self.bn2 = BatchNorm2d(64)
        self.block1 = Block(64, 128, reps=2, stride=2, start_with_relu=False)
        self.block2 = Block(128, 256, reps=2, stride=2, start_with_relu=
            True, grow_first=True)
        self.block3 = Block(256, 728, reps=2, stride=entry_block3_stride,
            start_with_relu=True, grow_first=True, is_last=True)
        self.block4 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block5 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block6 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block7 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block8 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block9 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block10 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block11 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block12 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block13 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block14 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block15 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block16 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block17 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block18 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block19 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, start_with_relu=True, grow_first=True)
        self.block20 = Block(728, 1024, reps=2, stride=1, dilation=
            exit_block_dilations[0], start_with_relu=True, grow_first=False,
            is_last=True)
        self.conv3 = SeparableConv2d_same(1024, 1536, 3, stride=1, dilation
            =exit_block_dilations[1])
        self.bn3 = BatchNorm2d(1536)
        self.conv4 = SeparableConv2d_same(1536, 1536, 3, stride=1, dilation
            =exit_block_dilations[1])
        self.bn4 = BatchNorm2d(1536)
        self.conv5 = SeparableConv2d_same(1536, 2048, 3, stride=1, dilation
            =exit_block_dilations[1])
        self.bn5 = BatchNorm2d(2048)
        self._init_weight()
        if pretrained:
            self._load_xception_pretrained()

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.block1(x)
        low_level_feat = x
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.block5(x)
        x = self.block6(x)
        x = self.block7(x)
        x = self.block8(x)
        x = self.block9(x)
        x = self.block10(x)
        x = self.block11(x)
        x = self.block12(x)
        x = self.block13(x)
        x = self.block14(x)
        x = self.block15(x)
        x = self.block16(x)
        x = self.block17(x)
        x = self.block18(x)
        x = self.block19(x)
        x = self.block20(x)
        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu(x)
        x = self.conv4(x)
        x = self.bn4(x)
        x = self.relu(x)
        x = self.conv5(x)
        x = self.bn5(x)
        x = self.relu(x)
        return x, low_level_feat

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _load_xception_pretrained(self):
        pretrain_dict = model_zoo.load_url(
            'http://data.lip6.fr/cadene/pretrainedmodels/xception-b5690688.pth'
            )
        model_dict = {}
        state_dict = self.state_dict()
        for k, v in pretrain_dict.items():
            if k in model_dict:
                if 'pointwise' in k:
                    v = v.unsqueeze(-1).unsqueeze(-1)
                if k.startswith('block11'):
                    model_dict[k] = v
                    model_dict[k.replace('block11', 'block12')] = v
                    model_dict[k.replace('block11', 'block13')] = v
                    model_dict[k.replace('block11', 'block14')] = v
                    model_dict[k.replace('block11', 'block15')] = v
                    model_dict[k.replace('block11', 'block16')] = v
                    model_dict[k.replace('block11', 'block17')] = v
                    model_dict[k.replace('block11', 'block18')] = v
                    model_dict[k.replace('block11', 'block19')] = v
                elif k.startswith('block12'):
                    model_dict[k.replace('block12', 'block20')] = v
                elif k.startswith('bn3'):
                    model_dict[k] = v
                    model_dict[k.replace('bn3', 'bn4')] = v
                elif k.startswith('conv4'):
                    model_dict[k.replace('conv4', 'conv5')] = v
                elif k.startswith('bn4'):
                    model_dict[k.replace('bn4', 'bn5')] = v
                else:
                    model_dict[k] = v
        state_dict.update(model_dict)
        self.load_state_dict(state_dict)


class ASPP_module(nn.Module):

    def __init__(self, inplanes, planes, dilation):
        super(ASPP_module, self).__init__()
        if dilation == 1:
            kernel_size = 1
            padding = 0
        else:
            kernel_size = 3
            padding = dilation
        self.atrous_convolution = nn.Conv2d(inplanes, planes, kernel_size=
            kernel_size, stride=1, padding=padding, dilation=dilation, bias
            =False)
        self.bn = BatchNorm2d(planes)
        self.relu = nn.ReLU()
        self._init_weight()

    def forward(self, x):
        x = self.atrous_convolution(x)
        x = self.bn(x)
        return self.relu(x)

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class DeepLabv3_plus(nn.Module):

    def __init__(self, nInputChannels=3, n_classes=21, os=16, pretrained=
        False, freeze_bn=False, _print=True):
        if _print:
            None
            None
            None
            None
            None
        super(DeepLabv3_plus, self).__init__()
        self.xception_features = Xception(nInputChannels, os, pretrained)
        if os == 16:
            dilations = [1, 6, 12, 18]
        elif os == 8:
            dilations = [1, 12, 24, 36]
        else:
            raise NotImplementedError
        self.aspp1 = ASPP_module(2048, 256, dilation=dilations[0])
        self.aspp2 = ASPP_module(2048, 256, dilation=dilations[1])
        self.aspp3 = ASPP_module(2048, 256, dilation=dilations[2])
        self.aspp4 = ASPP_module(2048, 256, dilation=dilations[3])
        self.relu = nn.ReLU()
        self.global_avg_pool = nn.Sequential(nn.AdaptiveAvgPool2d((1, 1)),
            nn.Conv2d(2048, 256, 1, stride=1, bias=False), BatchNorm2d(256),
            nn.ReLU())
        self.conv1 = nn.Conv2d(1280, 256, 1, bias=False)
        self.bn1 = BatchNorm2d(256)
        self.conv2 = nn.Conv2d(128, 48, 1, bias=False)
        self.bn2 = BatchNorm2d(48)
        self.last_conv = nn.Sequential(nn.Conv2d(304, 256, kernel_size=3,
            stride=1, padding=1, bias=False), BatchNorm2d(256), nn.ReLU(),
            nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1, bias=
            False), BatchNorm2d(256), nn.ReLU(), nn.Conv2d(256, n_classes,
            kernel_size=1, stride=1))
        if freeze_bn:
            self._freeze_bn()

    def forward(self, input):
        x, low_level_features = self.xception_features(input)
        x1 = self.aspp1(x)
        x2 = self.aspp2(x)
        x3 = self.aspp3(x)
        x4 = self.aspp4(x)
        x5 = self.global_avg_pool(x)
        x5 = F.interpolate(x5, size=x4.size()[2:], mode='bilinear',
            align_corners=True)
        x = torch.cat((x1, x2, x3, x4, x5), dim=1)
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = F.interpolate(x, size=(int(math.ceil(input.size()[-2] / 4)),
            int(math.ceil(input.size()[-1] / 4))), mode='bilinear',
            align_corners=True)
        low_level_features = self.conv2(low_level_features)
        low_level_features = self.bn2(low_level_features)
        low_level_features = self.relu(low_level_features)
        x = torch.cat((x, low_level_features), dim=1)
        x = self.last_conv(x)
        x = F.interpolate(x, size=input.size()[2:], mode='bilinear',
            align_corners=True)
        return x

    def _freeze_bn(self):
        for m in self.modules():
            if isinstance(m, BatchNorm2d):
                m.eval()

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


def conv3x3(in_planes, out_planes, stride=1, padding=1, dilation=1):
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
        padding=padding, bias=False, dilation=dilation)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None,
        dilation=(1, 1), residual=True, BatchNorm=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride, padding=dilation[0],
            dilation=dilation[0])
        self.bn1 = BatchNorm(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes, padding=dilation[1], dilation=
            dilation[1])
        self.bn2 = BatchNorm(planes)
        self.downsample = downsample
        self.stride = stride
        self.residual = residual

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        if self.residual:
            out += residual
        out = self.relu(out)
        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None,
        dilation=(1, 1), residual=True, BatchNorm=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = BatchNorm(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
            padding=dilation[1], bias=False, dilation=dilation[1])
        self.bn2 = BatchNorm(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = BatchNorm(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

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
        return out


class DRN(nn.Module):

    def __init__(self, block, layers, arch='D', channels=(16, 32, 64, 128, 
        256, 512, 512, 512), BatchNorm=None):
        super(DRN, self).__init__()
        self.inplanes = channels[0]
        self.out_dim = channels[-1]
        self.arch = arch
        if arch == 'C':
            self.conv1 = nn.Conv2d(3, channels[0], kernel_size=7, stride=1,
                padding=3, bias=False)
            self.bn1 = BatchNorm(channels[0])
            self.relu = nn.ReLU(inplace=True)
            self.layer1 = self._make_layer(BasicBlock, channels[0], layers[
                0], stride=1, BatchNorm=BatchNorm)
            self.layer2 = self._make_layer(BasicBlock, channels[1], layers[
                1], stride=2, BatchNorm=BatchNorm)
        elif arch == 'D':
            self.layer0 = nn.Sequential(nn.Conv2d(3, channels[0],
                kernel_size=7, stride=1, padding=3, bias=False), BatchNorm(
                channels[0]), nn.ReLU(inplace=True))
            self.layer1 = self._make_conv_layers(channels[0], layers[0],
                stride=1, BatchNorm=BatchNorm)
            self.layer2 = self._make_conv_layers(channels[1], layers[1],
                stride=2, BatchNorm=BatchNorm)
        self.layer3 = self._make_layer(block, channels[2], layers[2],
            stride=2, BatchNorm=BatchNorm)
        self.layer4 = self._make_layer(block, channels[3], layers[3],
            stride=2, BatchNorm=BatchNorm)
        self.layer5 = self._make_layer(block, channels[4], layers[4],
            dilation=2, new_level=False, BatchNorm=BatchNorm)
        self.layer6 = None if layers[5] == 0 else self._make_layer(block,
            channels[5], layers[5], dilation=4, new_level=False, BatchNorm=
            BatchNorm)
        if arch == 'C':
            self.layer7 = None if layers[6] == 0 else self._make_layer(
                BasicBlock, channels[6], layers[6], dilation=2, new_level=
                False, residual=False, BatchNorm=BatchNorm)
            self.layer8 = None if layers[7] == 0 else self._make_layer(
                BasicBlock, channels[7], layers[7], dilation=1, new_level=
                False, residual=False, BatchNorm=BatchNorm)
        elif arch == 'D':
            self.layer7 = None if layers[6] == 0 else self._make_conv_layers(
                channels[6], layers[6], dilation=2, BatchNorm=BatchNorm)
            self.layer8 = None if layers[7] == 0 else self._make_conv_layers(
                channels[7], layers[7], dilation=1, BatchNorm=BatchNorm)
        self._init_weight()

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, SynchronizedBatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1, dilation=1,
        new_level=True, residual=True, BatchNorm=None):
        assert dilation == 1 or dilation % 2 == 0
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm(planes * block.expansion))
        layers = list()
        layers.append(block(self.inplanes, planes, stride, downsample,
            dilation=(1, 1) if dilation == 1 else (dilation // 2 if
            new_level else dilation, dilation), residual=residual,
            BatchNorm=BatchNorm))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, residual=residual,
                dilation=(dilation, dilation), BatchNorm=BatchNorm))
        return nn.Sequential(*layers)

    def _make_conv_layers(self, channels, convs, stride=1, dilation=1,
        BatchNorm=None):
        modules = []
        for i in range(convs):
            modules.extend([nn.Conv2d(self.inplanes, channels, kernel_size=
                3, stride=stride if i == 0 else 1, padding=dilation, bias=
                False, dilation=dilation), BatchNorm(channels), nn.ReLU(
                inplace=True)])
            self.inplanes = channels
        return nn.Sequential(*modules)

    def forward(self, x):
        if self.arch == 'C':
            x = self.conv1(x)
            x = self.bn1(x)
            x = self.relu(x)
        elif self.arch == 'D':
            x = self.layer0(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        low_level_feat = x
        x = self.layer4(x)
        x = self.layer5(x)
        if self.layer6 is not None:
            x = self.layer6(x)
        if self.layer7 is not None:
            x = self.layer7(x)
        if self.layer8 is not None:
            x = self.layer8(x)
        return x, low_level_feat


class DRN_A(nn.Module):

    def __init__(self, block, layers, BatchNorm=None):
        self.inplanes = 64
        super(DRN_A, self).__init__()
        self.out_dim = 512 * block.expansion
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
            bias=False)
        self.bn1 = BatchNorm(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0], BatchNorm=
            BatchNorm)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2,
            BatchNorm=BatchNorm)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=1,
            dilation=2, BatchNorm=BatchNorm)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=1,
            dilation=4, BatchNorm=BatchNorm)
        self._init_weight()

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, SynchronizedBatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1, dilation=1,
        BatchNorm=None):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm(planes * block.expansion))
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample,
            BatchNorm=BatchNorm))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, dilation=(dilation,
                dilation), BatchNorm=BatchNorm))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x


class InvertedResidual(nn.Module):

    def __init__(self, inp, oup, stride, dilation, expand_ratio, BatchNorm):
        super(InvertedResidual, self).__init__()
        self.stride = stride
        assert stride in [1, 2]
        hidden_dim = round(inp * expand_ratio)
        self.use_res_connect = self.stride == 1 and inp == oup
        self.kernel_size = 3
        self.dilation = dilation
        if expand_ratio == 1:
            self.conv = nn.Sequential(nn.Conv2d(hidden_dim, hidden_dim, 3,
                stride, 0, dilation, groups=hidden_dim, bias=False),
                BatchNorm(hidden_dim), nn.ReLU6(inplace=True), nn.Conv2d(
                hidden_dim, oup, 1, 1, 0, 1, 1, bias=False), BatchNorm(oup))
        else:
            self.conv = nn.Sequential(nn.Conv2d(inp, hidden_dim, 1, 1, 0, 1,
                bias=False), BatchNorm(hidden_dim), nn.ReLU6(inplace=True),
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 0, dilation,
                groups=hidden_dim, bias=False), BatchNorm(hidden_dim), nn.
                ReLU6(inplace=True), nn.Conv2d(hidden_dim, oup, 1, 1, 0, 1,
                bias=False), BatchNorm(oup))

    def forward(self, x):
        x_pad = fixed_padding(x, self.kernel_size, dilation=self.dilation)
        if self.use_res_connect:
            x = x + self.conv(x_pad)
        else:
            x = self.conv(x_pad)
        return x


def conv_bn(inp, oup, stride, BatchNorm):
    return nn.Sequential(nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
        BatchNorm(oup), nn.ReLU6(inplace=True))


class MobileNetV2(nn.Module):

    def __init__(self, output_stride=8, BatchNorm=None, width_mult=1.0,
        pretrained=True):
        super(MobileNetV2, self).__init__()
        block = InvertedResidual
        input_channel = 32
        current_stride = 1
        rate = 1
        interverted_residual_setting = [[1, 16, 1, 1], [6, 24, 2, 2], [6, 
            32, 3, 2], [6, 64, 4, 2], [6, 96, 3, 1], [6, 160, 3, 2], [6, 
            320, 1, 1]]
        input_channel = int(input_channel * width_mult)
        self.features = [conv_bn(3, input_channel, 2, BatchNorm)]
        current_stride *= 2
        for t, c, n, s in interverted_residual_setting:
            if current_stride == output_stride:
                stride = 1
                dilation = rate
                rate *= s
            else:
                stride = s
                dilation = 1
                current_stride *= s
            output_channel = int(c * width_mult)
            for i in range(n):
                if i == 0:
                    self.features.append(block(input_channel,
                        output_channel, stride, dilation, t, BatchNorm))
                else:
                    self.features.append(block(input_channel,
                        output_channel, 1, dilation, t, BatchNorm))
                input_channel = output_channel
        self.features = nn.Sequential(*self.features)
        self._initialize_weights()
        if pretrained:
            self._load_pretrained_model()
        self.low_level_features = self.features[0:4]
        self.high_level_features = self.features[4:]

    def forward(self, x):
        low_level_feat = self.low_level_features(x)
        x = self.high_level_features(low_level_feat)
        return x, low_level_feat

    def _load_pretrained_model(self):
        pretrain_dict = model_zoo.load_url(
            'http://jeff95.me/models/mobilenet_v2-6a65762b.pth')
        model_dict = {}
        state_dict = self.state_dict()
        for k, v in pretrain_dict.items():
            if k in state_dict:
                model_dict[k] = v
        state_dict.update(model_dict)
        self.load_state_dict(state_dict)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, SynchronizedBatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, dilation=1, downsample=
        None, BatchNorm=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = BatchNorm(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
            dilation=dilation, padding=dilation, bias=False)
        self.bn2 = BatchNorm(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = BatchNorm(planes * 4)
        self.downsample = downsample
        self.stride = stride
        self.dilation = dilation

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out = self.conv3(out)
        out = self.bn3(out)
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)
        return out


class ResNet(nn.Module):

    def __init__(self, block, layers, output_stride, BatchNorm, pretrained=True
        ):
        self.inplanes = 64
        super(ResNet, self).__init__()
        blocks = [1, 2, 4]
        if output_stride == 16:
            strides = [1, 2, 2, 1]
            dilations = [1, 1, 1, 2]
        elif output_stride == 8:
            strides = [1, 2, 1, 1]
            dilations = [1, 1, 2, 4]
        else:
            raise NotImplementedError
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
            bias=False)
        self.bn1 = BatchNorm(64)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0], stride=strides
            [0], dilation=dilations[0], BatchNorm=BatchNorm)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=
            strides[1], dilation=dilations[1], BatchNorm=BatchNorm)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=
            strides[2], dilation=dilations[2], BatchNorm=BatchNorm)
        self.layer4 = self._make_MG_unit(block, 512, blocks=blocks, stride=
            strides[3], dilation=dilations[3], BatchNorm=BatchNorm)
        self._init_weight()
        if pretrained:
            self._load_pretrained_model()

    def _make_layer(self, block, planes, blocks, stride=1, dilation=1,
        BatchNorm=None):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm(planes * block.expansion))
        layers = []
        layers.append(block(self.inplanes, planes, stride, dilation,
            downsample, BatchNorm))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, dilation=dilation,
                BatchNorm=BatchNorm))
        return nn.Sequential(*layers)

    def _make_MG_unit(self, block, planes, blocks, stride=1, dilation=1,
        BatchNorm=None):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(nn.Conv2d(self.inplanes, planes *
                block.expansion, kernel_size=1, stride=stride, bias=False),
                BatchNorm(planes * block.expansion))
        layers = []
        layers.append(block(self.inplanes, planes, stride, dilation=blocks[
            0] * dilation, downsample=downsample, BatchNorm=BatchNorm))
        self.inplanes = planes * block.expansion
        for i in range(1, len(blocks)):
            layers.append(block(self.inplanes, planes, stride=1, dilation=
                blocks[i] * dilation, BatchNorm=BatchNorm))
        return nn.Sequential(*layers)

    def forward(self, input):
        x = self.conv1(input)
        x = self.bn1(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        low_level_feat = x
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x, low_level_feat

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, SynchronizedBatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _load_pretrained_model(self):
        pretrain_dict = model_zoo.load_url(
            'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth')
        model_dict = {}
        state_dict = self.state_dict()
        for k, v in pretrain_dict.items():
            if k in state_dict:
                model_dict[k] = v
        state_dict.update(model_dict)
        self.load_state_dict(state_dict)


class SeparableConv2d(nn.Module):

    def __init__(self, inplanes, planes, kernel_size=3, stride=1, dilation=
        1, bias=False, BatchNorm=None):
        super(SeparableConv2d, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, inplanes, kernel_size, stride, 0,
            dilation, groups=inplanes, bias=bias)
        self.bn = BatchNorm(inplanes)
        self.pointwise = nn.Conv2d(inplanes, planes, 1, 1, 0, 1, 1, bias=bias)

    def forward(self, x):
        x = fixed_padding(x, self.conv1.kernel_size[0], dilation=self.conv1
            .dilation[0])
        x = self.conv1(x)
        x = self.bn(x)
        x = self.pointwise(x)
        return x


class Block(nn.Module):

    def __init__(self, inplanes, planes, reps, stride=1, dilation=1,
        BatchNorm=None, start_with_relu=True, grow_first=True, is_last=
        False, skip=None):
        super(Block, self).__init__()
        if planes != inplanes or stride != 1:
            self.skip = nn.Conv2d(inplanes, planes, 1, stride=stride, bias=
                False)
            self.skipbn = BatchNorm(planes)
        elif skip is not None:
            if skip == 'conv':
                self.skip = nn.Conv2d(inplanes, planes, 1, stride=stride,
                    bias=False)
                self.skipbn = BatchNorm(planes)
        else:
            self.skip = None
        self.relu = nn.ReLU()
        rep = []
        filters = inplanes
        if grow_first:
            rep.append(self.relu)
            rep.append(SeparableConv2d(inplanes, planes, 3, 1, dilation,
                BatchNorm=BatchNorm))
            rep.append(BatchNorm(planes))
            filters = planes
        for i in range(reps - 1):
            rep.append(self.relu)
            rep.append(SeparableConv2d(filters, filters, 3, 1, dilation,
                BatchNorm=BatchNorm))
            rep.append(BatchNorm(filters))
        if not grow_first:
            rep.append(self.relu)
            rep.append(SeparableConv2d(inplanes, planes, 3, 1, dilation,
                BatchNorm=BatchNorm))
            rep.append(BatchNorm(planes))
        if stride != 1:
            rep.append(self.relu)
            rep.append(SeparableConv2d(planes, planes, 3, 2, BatchNorm=
                BatchNorm))
            rep.append(BatchNorm(planes))
        if stride == 1 and is_last:
            rep.append(self.relu)
            rep.append(SeparableConv2d(planes, planes, 3, 1, BatchNorm=
                BatchNorm))
            rep.append(BatchNorm(planes))
        if not start_with_relu:
            rep = rep[1:]
        self.rep = nn.Sequential(*rep)

    def forward(self, inp):
        x = self.rep(inp)
        if self.skip is not None:
            skip = self.skip(inp)
            skip = self.skipbn(skip)
        else:
            skip = inp
        x = x + skip
        return x


class AlignedXception(nn.Module):
    """
    Modified Alighed Xception
    """

    def __init__(self, output_stride, BatchNorm, pretrained=False, mode=
        'xception_71'):
        super(AlignedXception, self).__init__()
        if output_stride == 16:
            entry_block3_stride = 2
            middle_block_dilation = 1
            exit_block_dilations = 1, 2
        elif output_stride == 8:
            entry_block3_stride = 1
            middle_block_dilation = 2
            exit_block_dilations = 2, 4
        else:
            raise NotImplementedError
        self.conv1 = nn.Conv2d(3, 32, 3, stride=2, padding=1, bias=False)
        self.bn1 = BatchNorm(32)
        self.relu = nn.ReLU()
        self.block0_0 = nn.Sequential(self.conv1, self.bn1, self.relu)
        self.conv2 = nn.Conv2d(32, 64, 3, stride=1, padding=1, bias=False)
        self.bn2 = BatchNorm(64)
        self.block0_1 = nn.Sequential(self.conv2, self.bn2, self.relu)
        self.block1 = Block(64, 128, reps=2, stride=2, BatchNorm=BatchNorm,
            start_with_relu=False)
        if mode == 'xception_71':
            self.block2_0 = Block(128, 256, reps=2, stride=2, BatchNorm=
                BatchNorm, start_with_relu=False, grow_first=True)
            self.block2_1 = Block(256, 256, reps=2, stride=1, BatchNorm=
                BatchNorm, start_with_relu=False, is_last=True, grow_first=
                True, skip='conv')
            self.block2 = nn.Sequential(self.block2_0, self.block2_1)
        elif mode == 'xception_65':
            self.block2 = Block(128, 256, reps=2, stride=2, BatchNorm=
                BatchNorm, start_with_relu=False, grow_first=True)
        if mode == 'xception_71':
            self.block3_0 = Block(256, 728, reps=3, stride=
                entry_block3_stride, BatchNorm=BatchNorm, start_with_relu=
                True, grow_first=True)
            self.block3_1 = Block(728, 728, reps=2, stride=1, BatchNorm=
                BatchNorm, start_with_relu=True, grow_first=True, is_last=
                True, skip='conv')
            self.block3 = nn.Sequential(self.block3_0, self.block3_1)
        if mode == 'xception_65':
            self.block3 = Block(256, 728, reps=2, stride=
                entry_block3_stride, BatchNorm=BatchNorm, start_with_relu=
                True, grow_first=True, is_last=True)
        self.entry_flow = nn.Sequential(self.conv1, self.bn1, self.relu,
            self.conv2, self.bn2, self.block1, self.block2, self.block3)
        self.block4 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block5 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block6 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block7 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block8 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block9 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block10 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block11 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block12 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block13 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block14 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block15 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block16 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block17 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block18 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block19 = Block(728, 728, reps=3, stride=1, dilation=
            middle_block_dilation, BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=True)
        self.block20 = Block(728, 1024, reps=2, stride=1, dilation=
            exit_block_dilations[0], BatchNorm=BatchNorm, start_with_relu=
            True, grow_first=False, is_last=True)
        self.conv3 = SeparableConv2d(1024, 1536, 3, stride=1, dilation=
            exit_block_dilations[1], BatchNorm=BatchNorm)
        self.bn3 = BatchNorm(1536)
        self.conv4 = SeparableConv2d(1536, 1536, 3, stride=1, dilation=
            exit_block_dilations[1], BatchNorm=BatchNorm)
        self.bn4 = BatchNorm(1536)
        self.conv5 = SeparableConv2d(1536, 2048, 3, stride=1, dilation=
            exit_block_dilations[1], BatchNorm=BatchNorm)
        self.bn5 = BatchNorm(2048)
        self.exit_flow = nn.Sequential(self.block20, self.conv3, self.bn3,
            self.conv4, self.bn4, self.conv5, self.bn5)
        self._init_weight()
        if pretrained:
            self._load_pretrained_model()

    def forward(self, x):
        x = self.block0_0(x)
        x = self.block0_1(x)
        x = self.block1(x)
        x = self.relu(x)
        x = self.block2(x)
        low_level_feat = x
        x = self.block3(x)
        x = self.block4(x)
        x = self.block5(x)
        x = self.block6(x)
        x = self.block7(x)
        x = self.block8(x)
        x = self.block9(x)
        x = self.block10(x)
        x = self.block11(x)
        x = self.block12(x)
        x = self.block13(x)
        x = self.block14(x)
        x = self.block15(x)
        x = self.block16(x)
        x = self.block17(x)
        x = self.block18(x)
        x = self.block19(x)
        x = self.block20(x)
        x = self.relu(x)
        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu(x)
        x = self.conv4(x)
        x = self.bn4(x)
        x = self.relu(x)
        x = self.conv5(x)
        x = self.bn5(x)
        x = self.relu(x)
        return x, low_level_feat

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, SynchronizedBatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _load_pretrained_model(self):
        pretrain_dict = model_zoo.load_url(
            'http://data.lip6.fr/cadene/pretrainedmodels/xception-b5690688.pth'
            )
        model_dict = {}
        state_dict = self.state_dict()
        for k, v in pretrain_dict.items():
            if k in model_dict:
                if 'pointwise' in k:
                    v = v.unsqueeze(-1).unsqueeze(-1)
                if k.startswith('block11'):
                    model_dict[k] = v
                    model_dict[k.replace('block11', 'block12')] = v
                    model_dict[k.replace('block11', 'block13')] = v
                    model_dict[k.replace('block11', 'block14')] = v
                    model_dict[k.replace('block11', 'block15')] = v
                    model_dict[k.replace('block11', 'block16')] = v
                    model_dict[k.replace('block11', 'block17')] = v
                    model_dict[k.replace('block11', 'block18')] = v
                    model_dict[k.replace('block11', 'block19')] = v
                elif k.startswith('block12'):
                    model_dict[k.replace('block12', 'block20')] = v
                elif k.startswith('bn3'):
                    model_dict[k] = v
                    model_dict[k.replace('bn3', 'bn4')] = v
                elif k.startswith('conv4'):
                    model_dict[k.replace('conv4', 'conv5')] = v
                elif k.startswith('bn4'):
                    model_dict[k.replace('bn4', 'bn5')] = v
                else:
                    model_dict[k] = v
        state_dict.update(model_dict)
        self.load_state_dict(state_dict)


class Decoder(nn.Module):

    def __init__(self, num_classes, backbone, BatchNorm, args, separate):
        super(Decoder, self).__init__()
        if backbone == 'resnet' or backbone == 'drn':
            low_level_inplanes = 256
        elif backbone == 'xception':
            low_level_inplanes = 256
        elif backbone == 'mobilenet':
            low_level_inplanes = 24
        elif backbone == 'autodeeplab':
            low_level_inplanes = args.filter_multiplier * args.steps
        else:
            raise NotImplementedError
        self.conv_feature = nn.Conv2d(low_level_inplanes, 48, 1, bias=False)
        self.bn1 = BatchNorm(48)
        self.feature_projection = nn.Sequential(self.conv_feature, self.bn1)
        concate_channel = 48 + 256
        if separate:
            self.conv1 = nn.Sequential(SeparateConv(concate_channel, 256,
                kernel_size=3, stride=1, padding=1, bias=False, BatchNorm=
                BatchNorm), nn.Dropout(0.5))
            self.conv2 = nn.Sequential(SeparateConv(256, 256, kernel_size=3,
                stride=1, padding=1, bias=False, BatchNorm=BatchNorm), nn.
                Dropout(0.1))
        else:
            self.conv1 = nn.Sequential(nn.Conv2d(concate_channel, 256,
                kernel_size=3, stride=1, padding=1, bias=False), BatchNorm(256)
                )
            self.conv2 = nn.Sequential(nn.Conv2d(256, 256, kernel_size=3,
                stride=1, padding=1, bias=False), BatchNorm(256))
        self.last_linear = nn.Conv2d(256, num_classes, kernel_size=1, stride=1)
        self._init_weight()

    def forward(self, x, low_level_feat):
        low_level_feat = self.feature_projection(low_level_feat)
        x = F.interpolate(x, size=low_level_feat.size()[2:], mode=
            'bilinear', align_corners=True)
        x = torch.cat((x, low_level_feat), dim=1)
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.last_linear(x)
        return x

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None:
                    nn.init.constant_(ly.bias, 0)


def build_aspp(backbone, output_stride, BatchNorm, args, separate):
    return ASPP_train(backbone, output_stride, args.filter_multiplier, 5,
        BatchNorm, separate)


def get_default_cell():
    cell = np.zeros((10, 2))
    cell[0] = [0, 7]
    cell[1] = [1, 4]
    cell[2] = [2, 4]
    cell[3] = [3, 6]
    cell[4] = [5, 4]
    cell[5] = [8, 4]
    cell[6] = [11, 5]
    cell[7] = [13, 5]
    cell[8] = [19, 7]
    cell[9] = [18, 5]
    return cell.astype('uint8')


def get_default_arch():
    backbone = [1, 0, 0, 1, 2, 1, 2, 2, 3, 3, 2, 1]
    cell_arch = get_default_cell()
    return network_layer_to_space(backbone), cell_arch, backbone


def get_default_net(args=None):
    filter_multiplier = args.filter_multiplier if args is not None else 20
    path_arch, cell_arch, backbone = get_default_arch()
    return newModel(path_arch, cell_arch, 19, 12, filter_multiplier=
        filter_multiplier, args=args)


def build_backbone(backbone, output_stride, BatchNorm, args):
    if backbone == 'resnet':
        return resnet.ResNet101(output_stride, BatchNorm)
    elif backbone == 'xception':
        return xception.AlignedXception(output_stride, BatchNorm)
    elif backbone == 'drn':
        return drn.drn_d_54(BatchNorm)
    elif backbone == 'mobilenet':
        return mobilenet.MobileNetV2(output_stride, BatchNorm)
    elif backbone == 'autodeeplab':
        return get_default_net(filter_multiplier=args.filter_multiplier)
    else:
        raise NotImplementedError


def build_decoder(num_classes, backbone, BatchNorm, args, separate):
    return Decoder(num_classes, backbone, BatchNorm, args, separate)


class DeepLab(nn.Module):

    def __init__(self, backbone='resnet', output_stride=16, num_classes=19,
        use_ABN=True, freeze_bn=False, args=None, separate=False):
        super(DeepLab, self).__init__()
        if backbone == 'drn':
            output_stride = 8
        if use_ABN:
            BatchNorm = ABN
        else:
            BatchNorm = NaiveBN
        self.backbone = build_backbone(backbone, output_stride, BatchNorm, args
            )
        self.aspp = build_aspp(backbone, output_stride, BatchNorm, args,
            separate)
        self.decoder = build_decoder(num_classes, backbone, BatchNorm, args,
            separate)
        if freeze_bn:
            self.freeze_bn()

    def forward(self, input_feature):
        x, low_level_feat = self.backbone(input_feature)
        x = self.aspp(x)
        x = self.decoder(x, low_level_feat)
        x = F.interpolate(x, size=input_feature.shape[2:], mode='bilinear',
            align_corners=True)
        return x

    def freeze_bn(self):
        for m in self.modules():
            if isinstance(m, ABN):
                m.eval()
            elif isinstance(m, nn.BatchNorm2d):
                m.eval()

    def get_1x_lr_params(self):
        modules = [self.backbone]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.Conv2d) or isinstance(m[1],
                    SynchronizedBatchNorm2d) or isinstance(m[1], nn.BatchNorm2d
                    ):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p

    def get_10x_lr_params(self):
        modules = [self.aspp, self.decoder]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.Conv2d) or isinstance(m[1],
                    SynchronizedBatchNorm2d) or isinstance(m[1], nn.BatchNorm2d
                    ):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p


ACT_ELU = 'elu'


ACT_LEAKY_RELU = 'leaky_relu'


ACT_RELU = 'relu'


class ABN(nn.Module):
    """Activated Batch Normalization

    This gathers a `BatchNorm2d` and an activation function in a single module
    """

    def __init__(self, num_features, eps=1e-05, momentum=0.1, affine=True,
        activation='leaky_relu', slope=0.01):
        """Creates an Activated Batch Normalization module

        Parameters
        ----------
        num_features : int
            Number of feature channels in the input and output.
        eps : float
            Small constant to prevent numerical issues.
        momentum : float
            Momentum factor applied to compute running statistics as.
        affine : bool
            If `True` apply learned scale and shift transformation after normalization.
        activation : str
            Name of the activation functions, one of: `leaky_relu`, `elu` or `none`.
        slope : float
            Negative slope for the `leaky_relu` activation.
        """
        super(ABN, self).__init__()
        self.num_features = num_features
        self.affine = affine
        self.eps = eps
        self.momentum = momentum
        self.activation = activation
        self.slope = slope
        if self.affine:
            self.weight = nn.Parameter(torch.ones(num_features))
            self.bias = nn.Parameter(torch.zeros(num_features))
        else:
            self.register_parameter('weight', None)
            self.register_parameter('bias', None)
        self.register_buffer('running_mean', torch.zeros(num_features))
        self.register_buffer('running_var', torch.ones(num_features))
        self.reset_parameters()

    def reset_parameters(self):
        nn.init.constant_(self.running_mean, 0)
        nn.init.constant_(self.running_var, 1)
        if self.affine:
            nn.init.constant_(self.weight, 1)
            nn.init.constant_(self.bias, 0)

    def forward(self, x):
        x = functional.batch_norm(x, self.running_mean, self.running_var,
            self.weight, self.bias, self.training, self.momentum, self.eps)
        if self.activation == ACT_RELU:
            return functional.relu(x, inplace=True)
        elif self.activation == ACT_LEAKY_RELU:
            return functional.leaky_relu(x, negative_slope=self.slope,
                inplace=True)
        elif self.activation == ACT_ELU:
            return functional.elu(x, inplace=True)
        else:
            return x

    def __repr__(self):
        rep = (
            '{name}({num_features}, eps={eps}, momentum={momentum}, affine={affine}, activation={activation}'
            )
        if self.activation == 'leaky_relu':
            rep += ', slope={slope})'
        else:
            rep += ')'
        return rep.format(name=self.__class__.__name__, **self.__dict__)


class GlobalAvgPool2d(nn.Module):

    def __init__(self):
        """Global average pooling over the input's spatial dimensions"""
        super(GlobalAvgPool2d, self).__init__()

    def forward(self, inputs):
        in_size = inputs.size()
        return inputs.view((in_size[0], in_size[1], -1)).mean(dim=2)


class SingleGPU(nn.Module):

    def __init__(self, module):
        super(SingleGPU, self).__init__()
        self.module = module

    def forward(self, input):
        return self.module(input)


class FutureResult(object):
    """A thread-safe future implementation. Used only as one-to-one pipe."""

    def __init__(self):
        self._result = None
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    def put(self, result):
        with self._lock:
            assert self._result is None, "Previous result has't been fetched."
            self._result = result
            self._cond.notify()

    def get(self):
        with self._lock:
            if self._result is None:
                self._cond.wait()
            res = self._result
            self._result = None
            return res


_SlavePipeBase = collections.namedtuple('_SlavePipeBase', ['identifier',
    'queue', 'result'])


class SlavePipe(_SlavePipeBase):
    """Pipe for master-slave communication."""

    def run_slave(self, msg):
        self.queue.put((self.identifier, msg))
        ret = self.result.get()
        self.queue.put(True)
        return ret


_MasterRegistry = collections.namedtuple('MasterRegistry', ['result'])


class SyncMaster(object):
    """An abstract `SyncMaster` object.
    - During the replication, as the data parallel will trigger an callback of each module, all slave devices should
    call `register(id)` and obtain an `SlavePipe` to communicate with the master.
    - During the forward pass, master device invokes `run_master`, all messages from slave devices will be collected,
    and passed to a registered callback.
    - After receiving the messages, the master device should gather the information and determine to message passed
    back to each slave devices.
    """

    def __init__(self, master_callback):
        """
        Args:
            master_callback: a callback to be invoked after having collected messages from slave devices.
        """
        self._master_callback = master_callback
        self._queue = queue.Queue()
        self._registry = collections.OrderedDict()
        self._activated = False

    def __getstate__(self):
        return {'master_callback': self._master_callback}

    def __setstate__(self, state):
        self.__init__(state['master_callback'])

    def register_slave(self, identifier):
        """
        Register an slave device.
        Args:
            identifier: an identifier, usually is the device id.
        Returns: a `SlavePipe` object which can be used to communicate with the master device.
        """
        if self._activated:
            assert self._queue.empty(
                ), 'Queue is not clean before next initialization.'
            self._activated = False
            self._registry.clear()
        future = FutureResult()
        self._registry[identifier] = _MasterRegistry(future)
        return SlavePipe(identifier, self._queue, future)

    def run_master(self, master_msg):
        """
        Main entry for the master device in each forward pass.
        The messages were first collected from each devices (including the master device), and then
        an callback will be invoked to compute the message to be sent back to each devices
        (including the master device).
        Args:
            master_msg: the message that the master want to send to itself. This will be placed as the first
            message when calling `master_callback`. For detailed usage, see `_SynchronizedBatchNorm` for an example.
        Returns: the message to be sent back to the master device.
        """
        self._activated = True
        intermediates = [(0, master_msg)]
        for i in range(self.nr_slaves):
            intermediates.append(self._queue.get())
        results = self._master_callback(intermediates)
        assert results[0][0
            ] == 0, 'The first result should belongs to the master.'
        for i, res in results:
            if i == 0:
                continue
            self._registry[i].result.put(res)
        for i in range(self.nr_slaves):
            assert self._queue.get() is True
        return results[0][1]

    @property
    def nr_slaves(self):
        return len(self._registry)


_ChildMessage = collections.namedtuple('_ChildMessage', ['sum', 'ssum',
    'sum_size'])


_MasterMessage = collections.namedtuple('_MasterMessage', ['sum', 'inv_std'])


def _sum_ft(tensor):
    """sum over the first and last dimention"""
    return tensor.sum(dim=0).sum(dim=-1)


def _unsqueeze_ft(tensor):
    """add new dementions at the front and the tail"""
    return tensor.unsqueeze(0).unsqueeze(-1)


class _SynchronizedBatchNorm(_BatchNorm):

    def __init__(self, num_features, eps=1e-05, momentum=0.1, affine=True):
        super(_SynchronizedBatchNorm, self).__init__(num_features, eps=eps,
            momentum=momentum, affine=affine)
        self._sync_master = SyncMaster(self._data_parallel_master)
        self._is_parallel = False
        self._parallel_id = None
        self._slave_pipe = None

    def forward(self, input):
        if not (self._is_parallel and self.training):
            return F.batch_norm(input, self.running_mean, self.running_var,
                self.weight, self.bias, self.training, self.momentum, self.eps)
        input_shape = input.size()
        input = input.view(input.size(0), self.num_features, -1)
        sum_size = input.size(0) * input.size(2)
        input_sum = _sum_ft(input)
        input_ssum = _sum_ft(input ** 2)
        if self._parallel_id == 0:
            mean, inv_std = self._sync_master.run_master(_ChildMessage(
                input_sum, input_ssum, sum_size))
        else:
            mean, inv_std = self._slave_pipe.run_slave(_ChildMessage(
                input_sum, input_ssum, sum_size))
        if self.affine:
            output = (input - _unsqueeze_ft(mean)) * _unsqueeze_ft(inv_std *
                self.weight) + _unsqueeze_ft(self.bias)
        else:
            output = (input - _unsqueeze_ft(mean)) * _unsqueeze_ft(inv_std)
        return output.view(input_shape)

    def __data_parallel_replicate__(self, ctx, copy_id):
        self._is_parallel = True
        self._parallel_id = copy_id
        if self._parallel_id == 0:
            ctx.sync_master = self._sync_master
        else:
            self._slave_pipe = ctx.sync_master.register_slave(copy_id)

    def _data_parallel_master(self, intermediates):
        """Reduce the sum and square-sum, compute the statistics, and broadcast it."""
        intermediates = sorted(intermediates, key=lambda i: i[1].sum.
            get_device())
        to_reduce = [i[1][:2] for i in intermediates]
        to_reduce = [j for i in to_reduce for j in i]
        target_gpus = [i[1].sum.get_device() for i in intermediates]
        sum_size = sum([i[1].sum_size for i in intermediates])
        sum_, ssum = ReduceAddCoalesced.apply(target_gpus[0], 2, *to_reduce)
        mean, inv_std = self._compute_mean_std(sum_, ssum, sum_size)
        broadcasted = Broadcast.apply(target_gpus, mean, inv_std)
        outputs = []
        for i, rec in enumerate(intermediates):
            outputs.append((rec[0], _MasterMessage(*broadcasted[i * 2:i * 2 +
                2])))
        return outputs

    def _compute_mean_std(self, sum_, ssum, size):
        """Compute the mean and standard-deviation with sum and square-sum. This method
        also maintains the moving average on the master device."""
        assert size > 1, 'BatchNorm computes unbiased standard-deviation, which requires size > 1.'
        mean = sum_ / size
        sumvar = ssum - sum_ * mean
        unbias_var = sumvar / (size - 1)
        bias_var = sumvar / size
        self.running_mean = (1 - self.momentum
            ) * self.running_mean + self.momentum * mean.data
        self.running_var = (1 - self.momentum
            ) * self.running_var + self.momentum * unbias_var.data
        return mean, bias_var.clamp(self.eps) ** -0.5


class CallbackContext(object):
    pass


def execute_replication_callbacks(modules):
    """
    Execute an replication callback `__data_parallel_replicate__` on each module created by original replication.
    The callback will be invoked with arguments `__data_parallel_replicate__(ctx, copy_id)`
    Note that, as all modules are isomorphism, we assign each sub-module with a context
    (shared among multiple copies of this module on different devices).
    Through this context, different copies can share some information.
    We guarantee that the callback on the master copy (the first copy) will be called ahead of calling the callback
    of any slave copies.
    """
    master_copy = modules[0]
    nr_modules = len(list(master_copy.modules()))
    ctxs = [CallbackContext() for _ in range(nr_modules)]
    for i, module in enumerate(modules):
        for j, m in enumerate(module.modules()):
            if hasattr(m, '__data_parallel_replicate__'):
                m.__data_parallel_replicate__(ctxs[j], i)


class DataParallelWithCallback(DataParallel):
    """
    Data Parallel with a replication callback.
    An replication callback `__data_parallel_replicate__` of each module will be invoked after being created by
    original `replicate` function.
    The callback will be invoked with arguments `__data_parallel_replicate__(ctx, copy_id)`
    Examples:
        > sync_bn = SynchronizedBatchNorm1d(10, eps=1e-5, affine=False)
        > sync_bn = DataParallelWithCallback(sync_bn, device_ids=[0, 1])
        # sync_bn.__data_parallel_replicate__ will be invoked.
    """

    def replicate(self, module, device_ids):
        modules = super(DataParallelWithCallback, self).replicate(module,
            device_ids)
        execute_replication_callbacks(modules)
        return modules


class NaiveBN(nn.Module):

    def __init__(self, C_out, momentum=0.1, affine=True):
        super(NaiveBN, self).__init__()
        self.op = nn.Sequential(nn.BatchNorm2d(C_out, affine=affine), nn.ReLU()
            )
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class ReLUConvBN(nn.Module):

    def __init__(self, C_in, C_out, kernel_size, stride, padding, affine=
        True, use_ABN=False):
        super(ReLUConvBN, self).__init__()
        if use_ABN:
            self.op = nn.Sequential(nn.Conv2d(C_in, C_out, kernel_size,
                stride=stride, padding=padding, bias=False), ABN(C_out))
        else:
            self.op = nn.Sequential(nn.ReLU(inplace=False), nn.Conv2d(C_in,
                C_out, kernel_size, stride=stride, padding=padding, bias=
                False), nn.BatchNorm2d(C_out, affine=affine))
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class DilConv(nn.Module):

    def __init__(self, C_in, C_out, kernel_size, stride, padding, dilation,
        affine=True, seperate=True, use_ABN=False):
        super(DilConv, self).__init__()
        if use_ABN:
            if seperate:
                self.op = nn.Sequential(nn.Conv2d(C_in, C_in, kernel_size=
                    kernel_size, stride=stride, padding=padding, dilation=
                    dilation, groups=C_in, bias=False), nn.Conv2d(C_in,
                    C_out, kernel_size=1, padding=0, bias=False), ABN(C_out,
                    affine=affine))
            else:
                self.op = nn.Sequential(nn.Conv2d(C_in, C_in, kernel_size=
                    kernel_size, stride=stride, padding=padding, dilation=
                    dilation, bias=False), nn.Conv2d(C_in, C_out,
                    kernel_size=1, padding=0, bias=False), ABN(C_out,
                    affine=affine))
        elif seperate:
            self.op = nn.Sequential(nn.ReLU(inplace=False), nn.Conv2d(C_in,
                C_in, kernel_size=kernel_size, stride=stride, padding=
                padding, dilation=dilation, groups=C_in, bias=False), nn.
                Conv2d(C_in, C_out, kernel_size=1, padding=0, bias=False),
                nn.BatchNorm2d(C_out, affine=affine))
        else:
            self.op = nn.Sequential(nn.ReLU(inplace=False), nn.Conv2d(C_in,
                C_in, kernel_size=kernel_size, stride=stride, padding=
                padding, dilation=dilation, bias=False), nn.Conv2d(C_in,
                C_out, kernel_size=1, padding=0, bias=False), nn.
                BatchNorm2d(C_out, affine=affine))
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class SepConv(nn.Module):

    def __init__(self, C_in, C_out, kernel_size, stride, padding, affine=
        True, use_ABN=False):
        super(SepConv, self).__init__()
        if use_ABN:
            self.op = nn.Sequential(nn.Conv2d(C_in, C_in, kernel_size=
                kernel_size, stride=stride, padding=padding, groups=C_in,
                bias=False), nn.Conv2d(C_in, C_in, kernel_size=1, padding=0,
                bias=False), ABN(C_in, affine=affine), nn.Conv2d(C_in, C_in,
                kernel_size=kernel_size, stride=1, padding=padding, groups=
                C_in, bias=False), nn.Conv2d(C_in, C_out, kernel_size=1,
                padding=0, bias=False), ABN(C_out, affine=affine))
        else:
            self.op = nn.Sequential(nn.ReLU(inplace=False), nn.Conv2d(C_in,
                C_in, kernel_size=kernel_size, stride=stride, padding=
                padding, groups=C_in, bias=False), nn.Conv2d(C_in, C_in,
                kernel_size=1, padding=0, bias=False), nn.BatchNorm2d(C_in,
                affine=affine), nn.ReLU(inplace=False), nn.Conv2d(C_in,
                C_in, kernel_size=kernel_size, stride=1, padding=padding,
                groups=C_in, bias=False), nn.Conv2d(C_in, C_out,
                kernel_size=1, padding=0, bias=False), nn.BatchNorm2d(C_out,
                affine=affine))
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class Identity(nn.Module):

    def __init__(self):
        super(Identity, self).__init__()
        self._initialize_weights()

    def forward(self, x):
        return x

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None:
                    nn.init.constant_(ly.bias, 0)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class Zero(nn.Module):

    def __init__(self, stride):
        super(Zero, self).__init__()
        self.stride = stride
        self._initialize_weights()

    def forward(self, x):
        if self.stride == 1:
            return x.mul(0.0)
        return x[:, :, ::self.stride, ::self.stride].mul(0.0)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class FactorizedReduce(nn.Module):

    def __init__(self, C_in, C_out, affine=True):
        super(FactorizedReduce, self).__init__()
        assert C_out % 2 == 0
        self.relu = nn.ReLU(inplace=False)
        self.conv_1 = nn.Conv2d(C_in, C_out // 2, 1, stride=2, padding=0,
            bias=False)
        self.conv_2 = nn.Conv2d(C_in, C_out // 2, 1, stride=2, padding=0,
            bias=False)
        self.bn = nn.BatchNorm2d(C_out, affine=affine)
        self._initialize_weights()

    def forward(self, x):
        x = self.relu(x)
        out = torch.cat([self.conv_1(x), self.conv_2(x[:, :, 1:, 1:])], dim=1)
        out = self.bn(out)
        return out

    def init_weight(self):
        for ly in self.children():
            if isinstance(ly, nn.Conv2d):
                nn.init.kaiming_normal_(ly.weight, a=1)
                if not ly.bias is None:
                    nn.init.constant_(ly.bias, 0)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class DoubleFactorizedReduce(nn.Module):

    def __init__(self, C_in, C_out, affine=True):
        super(DoubleFactorizedReduce, self).__init__()
        assert C_out % 2 == 0
        self.relu = nn.ReLU(inplace=False)
        self.conv_1 = nn.Conv2d(C_in, C_out // 2, 1, stride=4, padding=0,
            bias=False)
        self.conv_2 = nn.Conv2d(C_in, C_out // 2, 1, stride=4, padding=0,
            bias=False)
        self.bn = nn.BatchNorm2d(C_out, affine=affine)
        self._initialize_weights()

    def forward(self, x):
        x = self.relu(x)
        out = torch.cat([self.conv_1(x), self.conv_2(x[:, :, 1:, 1:])], dim=1)
        out = self.bn(out)
        return out

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class FactorizedIncrease(nn.Module):

    def __init__(self, in_channel, out_channel):
        super(FactorizedIncrease, self).__init__()
        self._in_channel = in_channel
        self.op = nn.Sequential(nn.Upsample(scale_factor=2, mode='bilinear'
            ), nn.ReLU(inplace=False), nn.Conv2d(self._in_channel,
            out_channel, 1, stride=1, padding=0), nn.BatchNorm2d(out_channel))
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class DoubleFactorizedIncrease(nn.Module):

    def __init__(self, in_channel, out_channel):
        super(DoubleFactorizedIncrease, self).__init__()
        self._in_channel = in_channel
        self.op = nn.Sequential(nn.Upsample(scale_factor=4, mode='bilinear'
            ), nn.ReLU(inplace=False), nn.Conv2d(self._in_channel,
            out_channel, 1, stride=1, padding=0), nn.BatchNorm2d(out_channel))
        self._initialize_weights()

    def forward(self, x):
        return self.op(x)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class ASPP(nn.Module):

    def __init__(self, in_channels, out_channels, paddings, dilations,
        momentum=0.0003):
        super(ASPP, self).__init__()
        self.conv11 = nn.Sequential(nn.Conv2d(in_channels, in_channels, 1,
            bias=False), nn.BatchNorm2d(in_channels))
        self.conv33 = nn.Sequential(nn.Conv2d(in_channels, in_channels, 3,
            padding=paddings, dilation=dilations, bias=False), nn.
            BatchNorm2d(in_channels))
        self.conv_p = nn.Sequential(nn.Conv2d(in_channels, in_channels, 1,
            bias=False), nn.BatchNorm2d(in_channels), nn.ReLU())
        self.concate_conv = nn.Conv2d(in_channels * 3, in_channels, 1, bias
            =False, stride=1, padding=0)
        self.concate_bn = nn.BatchNorm2d(in_channels, momentum)
        self.final_conv = nn.Conv2d(in_channels, out_channels, 1, bias=
            False, stride=1, padding=0)
        self._initialize_weights()

    def forward(self, x):
        conv11 = self.conv11(x)
        conv33 = self.conv33(x)
        image_pool = nn.AvgPool2d(kernel_size=x.size()[2:])
        upsample = nn.Upsample(size=x.size()[2:], mode='bilinear',
            align_corners=True)
        image_pool = image_pool(x)
        conv_image_pool = self.conv_p(image_pool)
        upsample = upsample(conv_image_pool)
        concate = torch.cat([conv11, conv33, upsample], dim=1)
        concate = self.concate_conv(concate)
        concate = self.concate_bn(concate)
        return self.final_conv(concate)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                if m.weight is not None:
                    m.weight.data.fill_(1)
                    m.bias.data.zero_()


class ASPP(nn.Module):

    def __init__(self, C, depth, num_classes, conv=nn.Conv2d, norm=NaiveBN,
        momentum=0.0003, mult=1):
        super(ASPP, self).__init__()
        self._C = C
        self._depth = depth
        self._num_classes = num_classes
        self.global_pooling = nn.AdaptiveAvgPool2d(1)
        self.aspp1 = conv(C, depth, kernel_size=1, stride=1, bias=False)
        self.aspp2 = conv(C, depth, kernel_size=3, stride=1, dilation=int(6 *
            mult), padding=int(6 * mult), bias=False)
        self.aspp3 = conv(C, depth, kernel_size=3, stride=1, dilation=int(
            12 * mult), padding=int(12 * mult), bias=False)
        self.aspp4 = conv(C, depth, kernel_size=3, stride=1, dilation=int(
            18 * mult), padding=int(18 * mult), bias=False)
        self.aspp5 = conv(C, depth, kernel_size=1, stride=1, bias=False)
        self.aspp1_bn = norm(depth, momentum)
        self.aspp2_bn = norm(depth, momentum)
        self.aspp3_bn = norm(depth, momentum)
        self.aspp4_bn = norm(depth, momentum)
        self.aspp5_bn = norm(depth, momentum)
        self.conv2 = conv(depth * 5, depth, kernel_size=1, stride=1, bias=False
            )
        self.bn2 = norm(depth, momentum)
        self._init_weight()

    def forward(self, x):
        x1 = self.aspp1(x)
        x1 = self.aspp1_bn(x1)
        x2 = self.aspp2(x)
        x2 = self.aspp2_bn(x2)
        x3 = self.aspp3(x)
        x3 = self.aspp3_bn(x3)
        x4 = self.aspp4(x)
        x4 = self.aspp4_bn(x4)
        x5 = self.global_pooling(x)
        x5 = self.aspp5(x5)
        x5 = self.aspp5_bn(x5)
        x5 = nn.Upsample((x.shape[2], x.shape[3]), mode='bilinear',
            align_corners=True)(x5)
        x = torch.cat((x1, x2, x3, x4, x5), 1)
        x = self.conv2(x)
        x = self.bn2(x)
        return x

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class Retrain_Autodeeplab(nn.Module):

    def __init__(self, args):
        super(Retrain_Autodeeplab, self).__init__()
        filter_param_dict = {(0): 1, (1): 2, (2): 4, (3): 8}
        BatchNorm2d = ABN if args.use_ABN else NaiveBN
        if (not args.dist and args.use_ABN or args.dist and args.use_ABN and
            dist.get_rank() == 0):
            None
        if args.net_arch is not None and args.cell_arch is not None:
            net_arch, cell_arch = np.load(args.net_arch), np.load(args.
                cell_arch)
        else:
            network_arch, cell_arch, network_path = get_default_arch()
        self.encoder = newModel(network_arch, cell_arch, args.num_classes, 
            12, args.filter_multiplier, BatchNorm=BatchNorm2d, args=args)
        self.aspp = ASPP(args.filter_multiplier * args.block_multiplier *
            filter_param_dict[network_path[-1]], 256, args.num_classes,
            conv=nn.Conv2d, norm=BatchNorm2d)
        self.decoder = Decoder(args.num_classes, filter_multiplier=args.
            filter_multiplier * args.block_multiplier, args=args,
            last_level=network_path[-1])

    def forward(self, x):
        encoder_output, low_level_feature = self.encoder(x)
        high_level_feature = self.aspp(encoder_output)
        decoder_output = self.decoder(high_level_feature, low_level_feature)
        return nn.Upsample((x.shape[2], x.shape[3]), mode='bilinear',
            align_corners=True)(decoder_output)

    def get_params(self):
        back_bn_params, back_no_bn_params = self.encoder.get_params()
        tune_wd_params = list(self.aspp.parameters()) + list(self.decoder.
            parameters()) + back_no_bn_params
        no_tune_wd_params = back_bn_params
        return tune_wd_params, no_tune_wd_params


class Decoder(nn.Module):

    def __init__(self, num_classes, filter_multiplier, BatchNorm=NaiveBN,
        args=None, last_level=0):
        super(Decoder, self).__init__()
        low_level_inplanes = filter_multiplier
        C_low = 48
        self.conv1 = nn.Conv2d(low_level_inplanes, C_low, 1, bias=False)
        self.bn1 = BatchNorm(48)
        self.last_conv = nn.Sequential(nn.Conv2d(304, 256, kernel_size=3,
            stride=1, padding=1, bias=False), BatchNorm(256), nn.Dropout(
            0.5), nn.Conv2d(256, 256, kernel_size=3, stride=1, padding=1,
            bias=False), BatchNorm(256), nn.Dropout(0.1), nn.Conv2d(256,
            num_classes, kernel_size=1, stride=1))
        self._init_weight()

    def forward(self, x, low_level_feat):
        low_level_feat = self.conv1(low_level_feat)
        low_level_feat = self.bn1(low_level_feat)
        x = F.interpolate(x, size=low_level_feat.size()[2:], mode=
            'bilinear', align_corners=True)
        x = torch.cat((x, low_level_feat), dim=1)
        x = self.last_conv(x)
        return x

    def _init_weight(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.kaiming_normal_(m.weight)
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()


class Cell(nn.Module):

    def __init__(self, steps, block_multiplier, prev_prev_fmultiplier,
        prev_filter_multiplier, cell_arch, network_arch, filter_multiplier,
        downup_sample, args=None):
        super(Cell, self).__init__()
        self.cell_arch = cell_arch
        self.C_in = block_multiplier * filter_multiplier
        self.C_out = filter_multiplier
        self.C_prev = int(block_multiplier * prev_filter_multiplier)
        self.C_prev_prev = int(block_multiplier * prev_prev_fmultiplier)
        self.downup_sample = downup_sample
        self.pre_preprocess = ReLUConvBN(self.C_prev_prev, self.C_out, 1, 1,
            0, args.affine, args.use_ABN)
        self.preprocess = ReLUConvBN(self.C_prev, self.C_out, 1, 1, 0, args
            .affine, args.use_ABN)
        self._steps = steps
        self.block_multiplier = block_multiplier
        self._ops = nn.ModuleList()
        if downup_sample == -1:
            self.scale = 0.5
        elif downup_sample == 1:
            self.scale = 2
        for x in self.cell_arch:
            primitive = PRIMITIVES[x[1]]
            op = OPS[primitive](self.C_out, stride=1, affine=args.affine,
                use_ABN=args.use_ABN)
            self._ops.append(op)

    def scale_dimension(self, dim, scale):
        return int((float(dim) - 1.0) * scale + 1.0) if dim % 2 == 1 else int(
            float(dim) * scale)

    def forward(self, prev_prev_input, prev_input):
        s0 = prev_prev_input
        s1 = prev_input
        if self.downup_sample != 0:
            feature_size_h = self.scale_dimension(s1.shape[2], self.scale)
            feature_size_w = self.scale_dimension(s1.shape[3], self.scale)
            s1 = F.interpolate(s1, [feature_size_h, feature_size_w], mode=
                'bilinear', align_corners=True)
        if s0.shape[2] != s1.shape[2] or s0.shape[3] != s1.shape[3]:
            s0 = F.interpolate(s0, (s1.shape[2], s1.shape[3]), mode=
                'bilinear', align_corners=True)
        s0 = self.pre_preprocess(s0) if s0.shape[1] != self.C_out else s0
        s1 = self.preprocess(s1)
        states = [s0, s1]
        offset = 0
        ops_index = 0
        for i in range(self._steps):
            new_states = []
            for j, h in enumerate(states):
                branch_index = offset + j
                if branch_index in self.cell_arch[:, (0)]:
                    if prev_prev_input is None and j == 0:
                        ops_index += 1
                        continue
                    new_state = self._ops[ops_index](h)
                    new_states.append(new_state)
                    ops_index += 1
            s = sum(new_states)
            offset += len(states)
            states.append(s)
        concat_feature = torch.cat(states[-self.block_multiplier:], dim=1)
        return prev_input, concat_feature


class newModel(nn.Module):

    def __init__(self, network_arch, cell_arch, num_classes, num_layers,
        filter_multiplier=20, lock_multiplier=5, step=5, cell=Cell,
        BatchNorm=NaiveBN, args=None):
        super(newModel, self).__init__()
        self.args = args
        self._step = step
        self.cells = nn.ModuleList()
        self.network_arch = torch.from_numpy(network_arch)
        self.cell_arch = torch.from_numpy(cell_arch)
        self._num_layers = num_layers
        self._num_classes = num_classes
        self._block_multiplier = args.block_multiplier
        self._filter_multiplier = args.filter_multiplier
        self.use_ABN = args.use_ABN
        initial_fm = 128 if args.initial_fm is None else args.initial_fm
        half_initial_fm = initial_fm // 2
        self.stem0 = nn.Sequential(nn.Conv2d(3, half_initial_fm, 3, stride=
            2, padding=1), BatchNorm(half_initial_fm))
        self.stem1 = nn.Sequential(nn.Conv2d(half_initial_fm,
            half_initial_fm, 3, padding=1), BatchNorm(half_initial_fm))
        ini_initial_fm = half_initial_fm
        self.stem2 = nn.Sequential(nn.Conv2d(half_initial_fm, initial_fm, 3,
            stride=2, padding=1), BatchNorm(initial_fm))
        filter_param_dict = {(0): 1, (1): 2, (2): 4, (3): 8}
        for i in range(self._num_layers):
            level_option = torch.sum(self.network_arch[i], dim=1)
            prev_level_option = torch.sum(self.network_arch[i - 1], dim=1)
            prev_prev_level_option = torch.sum(self.network_arch[i - 2], dim=1)
            level = torch.argmax(level_option).item()
            prev_level = torch.argmax(prev_level_option).item()
            prev_prev_level = torch.argmax(prev_prev_level_option).item()
            if i == 0:
                downup_sample = -torch.argmax(torch.sum(self.network_arch[0
                    ], dim=1))
                _cell = cell(self._step, self._block_multiplier, 
                    ini_initial_fm / args.block_multiplier, initial_fm /
                    args.block_multiplier, self.cell_arch, self.
                    network_arch[i], self._filter_multiplier *
                    filter_param_dict[level], downup_sample, self.args)
            else:
                three_branch_options = torch.sum(self.network_arch[i], dim=0)
                downup_sample = torch.argmax(three_branch_options).item() - 1
                if i == 1:
                    _cell = cell(self._step, self._block_multiplier, 
                        initial_fm / args.block_multiplier, self.
                        _filter_multiplier * filter_param_dict[prev_level],
                        self.cell_arch, self.network_arch[i], self.
                        _filter_multiplier * filter_param_dict[level],
                        downup_sample, self.args)
                else:
                    _cell = cell(self._step, self._block_multiplier, self.
                        _filter_multiplier * filter_param_dict[
                        prev_prev_level], self._filter_multiplier *
                        filter_param_dict[prev_level], self.cell_arch, self
                        .network_arch[i], self._filter_multiplier *
                        filter_param_dict[level], downup_sample, self.args)
            self.cells += [_cell]

    def forward(self, x):
        stem = self.stem0(x)
        stem0 = self.stem1(stem)
        stem1 = self.stem2(stem0)
        two_last_inputs = stem0, stem1
        for i in range(self._num_layers):
            two_last_inputs = self.cells[i](two_last_inputs[0],
                two_last_inputs[1])
            if i == 2:
                low_level_feature = two_last_inputs[1]
        last_output = two_last_inputs[-1]
        return last_output, low_level_feature

    def get_params(self):
        bn_params = []
        non_bn_params = []
        for name, param in self.named_parameters():
            if 'bn' in name or 'downsample.1' in name:
                bn_params.append(param)
            else:
                bn_params.append(param)
        return bn_params, non_bn_params


class OhemCELoss(nn.Module):

    def __init__(self, thresh, n_min, ignore_index=255, cuda=False, *args,
        **kwargs):
        super(OhemCELoss, self).__init__()
        self.thresh = thresh
        self.n_min = n_min
        self.ignore_lb = ignore_index
        self.criteria = nn.CrossEntropyLoss(ignore_index=ignore_index)
        if cuda:
            self.criteria = self.criteria

    def forward(self, logits, labels):
        N, C, H, W = logits.size()
        n_pixs = N * H * W
        logits = logits.permute(0, 2, 3, 1).contiguous().view(-1, C)
        labels = labels.view(-1)
        with torch.no_grad():
            scores = F.softmax(logits, dim=1)
            labels_cpu = labels
            invalid_mask = labels_cpu == self.ignore_lb
            labels_cpu[invalid_mask] = 0
            picks = scores[torch.arange(n_pixs), labels_cpu]
            picks[invalid_mask] = 1
            sorteds, _ = torch.sort(picks)
            thresh = self.thresh if sorteds[self.n_min
                ] < self.thresh else sorteds[self.n_min]
            labels[picks > thresh] = self.ignore_lb
        labels = labels.clone()
        loss = self.criteria(logits, labels)
        return loss


import torch
from _paritybench_helpers import _mock_config, _mock_layer, _paritybench_base, _fails_compile

class Test_NoamRosenberg_autodeeplab(_paritybench_base):
    pass
    @_fails_compile()
    def test_000(self):
        self._check(ABN(*[], **{'num_features': 4}), [torch.rand([4, 4, 4, 4])], {})

    @_fails_compile()
    def test_001(self):
        self._check(ASPP(*[], **{'C': 4, 'depth': 1, 'num_classes': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_002(self):
        self._check(Decoder(*[], **{'num_classes': 4, 'filter_multiplier': 4}), [torch.rand([4, 256, 64, 64]), torch.rand([4, 4, 4, 4])], {})

    def test_003(self):
        self._check(DilConv(*[], **{'C_in': 4, 'C_out': 4, 'kernel_size': 4, 'stride': 1, 'padding': 4, 'dilation': 1}), [torch.rand([4, 4, 4, 4])], {})

    def test_004(self):
        self._check(DoubleFactorizedIncrease(*[], **{'in_channel': 4, 'out_channel': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_005(self):
        self._check(DoubleFactorizedReduce(*[], **{'C_in': 4, 'C_out': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_006(self):
        self._check(FactorizedIncrease(*[], **{'in_channel': 4, 'out_channel': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_007(self):
        self._check(FactorizedReduce(*[], **{'C_in': 4, 'C_out': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_008(self):
        self._check(GlobalAvgPool2d(*[], **{}), [torch.rand([4, 4, 4, 4])], {})

    def test_009(self):
        self._check(Identity(*[], **{}), [torch.rand([4, 4, 4, 4])], {})

    @_fails_compile()
    def test_010(self):
        self._check(MixedOp(*[], **{'C': 4, 'stride': 1}), [torch.rand([4, 4, 4, 4]), torch.rand([4, 4, 4, 4])], {})

    def test_011(self):
        self._check(NaiveBN(*[], **{'C_out': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_012(self):
        self._check(ReLUConvBN(*[], **{'C_in': 4, 'C_out': 4, 'kernel_size': 4, 'stride': 1, 'padding': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_013(self):
        self._check(SepConv(*[], **{'C_in': 4, 'C_out': 4, 'kernel_size': 4, 'stride': 1, 'padding': 4}), [torch.rand([4, 4, 4, 4])], {})

    @_fails_compile()
    def test_014(self):
        self._check(SeparableConv2d_same(*[], **{'inplanes': 4, 'planes': 4}), [torch.rand([4, 4, 4, 4])], {})

    def test_015(self):
        self._check(Zero(*[], **{'stride': 1}), [torch.rand([4, 4, 4, 4])], {})

