# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import numpy as np
from deeppavlov.core.common.registry import register
from sklearn.decomposition import PCA


@register('emb_mat_assembler')
class EmbeddingsMatrixAssembler:
    """For a given Vocabulary assembles matrix of embeddings obtained from some `Embedder`. This
        class also can assemble embeddins of characters using

    Args:
        embedder: an instance of the class that convertes tokens to vectors.
            For example :class:`~deeppavlov.models.embedders.fasttext_embedder.FasttextEmbedder` or
            :class:`~deeppavlov.models.embedders.glove_embedder.GloVeEmbedder`
        vocab: instance of :class:`~deeppavlov.core.data.SimpleVocab`. The matrix of embeddings
            will be assembled relying on every token in the vocabulary. the indexing will match
            vocabulary indexing.
        character_level: whether to perform assembling on character level. This procedure will
            assemble matrix with embeddings for every character using averaged embeddings of
            words, that contain this character.
        emb_dim: dimensionality of the resulting embeddings. If not `None` it should be less
            or equal to the dimensionality of the embeddings provided by `Embedder`. The
            reduction of dimensionality is performed by taking main components of PCA.

    Attributes:
        dim: dimensionality of the embeddings (can be less than dimensionality of
            embeddings produced by `Embedder`.
    """

    def __init__(self, embedder, vocab, character_level=False, emb_dim=None, estimate_by_n=10000, *args, **kwargs):
        if emb_dim is None:
            emb_dim = embedder.dim
        self.emb_mat = np.zeros([len(vocab), emb_dim], dtype=np.float32)
        tokens_for_estimation = list(embedder)[:estimate_by_n]
        estimation_matrix = np.array([embedder([[word]])[0][0] for word in tokens_for_estimation], dtype=np.float32)
        emb_std = np.std(estimation_matrix)

        if emb_dim < embedder.dim:
            pca = PCA(n_components=emb_dim)
            pca.fit(estimation_matrix)
        elif emb_dim > embedder.dim:
            raise RuntimeError(f'Model dimension must be greater then requsted embeddings '
                               'dimension! model_dim = {embedder.dim}, requested_dim = {emb_dim}')
        else:
            pca = None
        for n, token in enumerate(vocab):
            if character_level:
                char_in_word_bool = np.array([token in word for word in tokens_for_estimation], dtype=bool)
                all_words_with_character = estimation_matrix[char_in_word_bool]
                if len(all_words_with_character) != 0:
                    if pca is not None:
                        all_words_with_character = pca.transform(all_words_with_character)
                    self.emb_mat[n] = sum(all_words_with_character) / len(all_words_with_character)
                else:
                    self.emb_mat[n] = np.random.randn(emb_dim) * np.std(self.emb_mat[:n])
            else:
                try:
                    if pca is not None:
                        self.emb_mat[n] = pca(embedder([[token]])[0])[0]
                    else:
                        self.emb_mat[n] = embedder([[token]])[0][0]

                except KeyError:
                    self.emb_mat[n] = np.random.randn(emb_dim) * emb_std

    @property
    def dim(self):
        return self.emb_mat.shape[1]


@register('random_emb_mat')
class RandomEmbeddingsMatrix:
    """Assembles matrix of random embeddings.

    Args:
        vocab_len: length of the vocabulary (number of tokens in it)
        emb_dim: dimensionality of the embeddings

    Attributes:
        dim: dimensionality of the embeddings
    """
    def __init__(self, vocab_len, emb_dim, *args, **kwargs):
        self.emb_mat = np.random.randn(vocab_len, emb_dim).astype(np.float32) / np.sqrt(emb_dim)

    @property
    def dim(self):
        return self.emb_mat.shape[1]
