"""
.. module:: TaggerBiRNNCRF
    :synopsis: TaggerBiRNNCRF is a model for sequences tagging that includes recurrent network + CRF.

.. moduleauthor:: Artem Chernodub
"""

import math

import torch
import torch.nn as nn

from classes.datasets_bank import DatasetsBank
from classes.utils import argsort_sequences_by_lens
from layers.layer_word_embeddings import LayerWordEmbeddings
from layers.layer_bilstm import LayerBiLSTM
from layers.layer_bigru import LayerBiGRU
from layers.layer_crf import LayerCRF
from models.tagger_base import TaggerBase

class TaggerBiRNNCRF(TaggerBase):
    def __init__(self, word_seq_indexer, tag_seq_indexer, class_num, batch_size=1, rnn_hidden_dim=100,
                 freeze_word_embeddings=False, dropout_ratio=0.5, rnn_type='GRU', gpu=-1):
        super(TaggerBiRNNCRF, self).__init__(word_seq_indexer, tag_seq_indexer, gpu, batch_size)
        self.tag_seq_indexer = tag_seq_indexer
        self.class_num = class_num
        self.rnn_hidden_dim = rnn_hidden_dim
        self.freeze_embeddings = freeze_word_embeddings
        self.dropout_ratio = dropout_ratio
        self.rnn_type = rnn_type
        self.gpu = gpu
        self.word_embeddings_layer = LayerWordEmbeddings(word_seq_indexer, gpu, freeze_word_embeddings)
        self.dropout = torch.nn.Dropout(p=dropout_ratio)
        if rnn_type == 'GRU':
            self.birnn_layer = LayerBiGRU(input_dim=self.word_embeddings_layer.output_dim,
                                          hidden_dim=rnn_hidden_dim,
                                          gpu=gpu)
        elif rnn_type == 'LSTM':
            self.birnn_layer = LayerBiLSTM(input_dim=self.word_embeddings_layer.output_dim,
                                           hidden_dim=rnn_hidden_dim,
                                           gpu=gpu)
        else:
            raise ValueError('Unknown rnn_type = %s, must be either "LSTM" or "GRU"')
        self.lin_layer = nn.Linear(in_features=self.birnn_layer.output_dim, out_features=class_num + 2)
        self.crf_layer = LayerCRF(gpu, states_num=class_num + 2, pad_idx=tag_seq_indexer.pad_idx, sos_idx=class_num + 1,
                                  tag_seq_indexer=tag_seq_indexer)
        if gpu >= 0:
            self.cuda(device=self.gpu)

    def _forward_birnn(self, word_sequences):
        word_seq_lens = [len(word_seq) for word_seq in word_sequences]
        z_word_embed = self.word_embeddings_layer(word_sequences)
        rnn_output_h = self.birnn_layer(z_word_embed, input_lens=word_seq_lens, pad_idx=self.word_seq_indexer.pad_idx)
        features_rnn_compressed = self.lin_layer(self.dropout(rnn_output_h)) # shape: batch_size x max_seq_len x class_num
        return features_rnn_compressed

    def get_loss(self, word_sequences_train_batch, tag_sequences_train_batch):
        targets_tensor_train_batch = self.tag_seq_indexer.items2tensor(tag_sequences_train_batch)
        mask = self.get_mask(word_sequences_train_batch)  # batch_num x max_seq_len
        features_rnn = self.apply_mask(self._forward_birnn(word_sequences_train_batch), mask)  # batch_num x max_seq_len x class_num
        numerator = self.crf_layer.numerator(features_rnn, targets_tensor_train_batch, mask)
        denominator = self.crf_layer.denominator(features_rnn, mask)
        nll_loss = -torch.mean(numerator - denominator)
        return nll_loss

    def predict_idx_from_words(self, word_sequences):
        self.eval()
        sort_indices, reverse_sort_indices = argsort_sequences_by_lens(word_sequences)
        word_sequences = DatasetsBank.get_sequences_by_indices(word_sequences, sort_indices)
        mask = self.get_mask(word_sequences)
        features_rnn_compressed = self.apply_mask(self._forward_birnn(word_sequences), mask)
        output_idx_sequences = self.crf_layer.decode_viterbi(features_rnn_compressed, mask)
        output_idx_sequences = DatasetsBank.get_sequences_by_indices(output_idx_sequences, reverse_sort_indices)
        return output_idx_sequences

    def predict_tags_from_words(self, word_sequences, batch_size=-1):
        if batch_size == -1:
            batch_size = self.batch_size
        print('\n')
        batch_num = math.floor(len(word_sequences) / batch_size)
        output_tag_sequences = list()
        for n in range(batch_num):
            i = n*batch_size
            if n < batch_num - 1:
                j = (n + 1)*batch_size
            else:
                j = len(word_sequences)
            curr_output_idx = self.predict_idx_from_words(word_sequences[i:j])
            curr_output_tag_sequences = self.tag_seq_indexer.idx2items(curr_output_idx)
            output_tag_sequences.extend(curr_output_tag_sequences)
            print('\r++ predicting, batch %d/%d (%1.2f%%).' % (n + 1, batch_num, math.ceil(n * 100.0 / batch_num)),
                  end='', flush=True)
        return output_tag_sequences
