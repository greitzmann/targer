import torch
import numpy as np
from sklearn.metrics import accuracy_score # f1_score, precision_score, recall_score
from classes.tag_component import TagComponent


class Evaluator():
    @staticmethod
    def get_accuracy_token_level(targets_tag_sequences, outputs_tag_sequences, tag_seq_indexer):
        targets_idx = tag_seq_indexer.elements2idx(targets_tag_sequences)
        outputs_idx = tag_seq_indexer.elements2idx(outputs_tag_sequences)
        y_true = [i for sequence in targets_idx for i in sequence]
        y_pred = [i for sequence in outputs_idx for i in sequence]
        return accuracy_score(y_true, y_pred) * 100

    @staticmethod
    def get_f1_from_words(targets_tag_sequences, outputs_tag_sequences, match_alpha_ratio=0.999):
        targets_tag_components_sequences = TagComponent.extract_tag_components_sequences(targets_tag_sequences)
        outputs_tag_components_sequences = TagComponent.extract_tag_components_sequences(outputs_tag_sequences)
        return Evaluator.get_f1_from_components_sequences(targets_tag_components_sequences,
                                                          outputs_tag_components_sequences,
                                                          match_alpha_ratio)

    @staticmethod
    def get_f1_from_components_sequences(targets_tag_components_sequences, outputs_tag_components_sequences, match_alpha_ratio):
        TP, FN, FP = 0, 0, 0
        for targets_tag_components, outputs_tag_components in zip(targets_tag_components_sequences, outputs_tag_components_sequences):
            for target_tc in targets_tag_components:
                found = False
                for output_tc in outputs_tag_components:
                    if output_tc.is_equal(target_tc, match_alpha_ratio):
                        found = True
                        break
                if found:
                    TP += 1
                else:
                    FN += 1
            for output_tc in outputs_tag_components:
                found = False
                for target_tc in targets_tag_components:
                    if target_tc.is_equal(output_tc, match_alpha_ratio):
                        found = True
                        break
                if not found:
                    FP += 1
        Precision = (TP / max(TP + FP, 1))*100
        Recall = (TP / max(TP + FN, 1))*100
        F1 = (2 * TP / max(2 * TP + FP + FN, 1))*100
        return F1, Precision, Recall, (TP, FP, FN)

    @staticmethod
    def write_text_report(fn, args, scores_report_str):
        text_file = open(fn, mode='w')
        for hyper_param in str(args).replace('Namespace(', '').replace(')', '').split(', '):
            text_file.write('%s\n' % hyper_param)
        text_file.write(scores_report_str)
        text_file.close()
