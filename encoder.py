import tensorflow as tf
import tensorflow.keras.backend as K
from layers import MultiHeadAttention
from data import generate_data

class ResidualBlock_BN(tf.keras.layers.Layer):
	def __init__(self, MHA, BN, **kwargs):
		super().__init__(**kwargs)
		self.MHA = MHA
		self.BN = BN

	def call(self, x, mask = None, training = True):
		if mask is None:
			return self.BN(x + self.MHA(x), training = training)
		else:
			return self.BN(x + self.MHA(x, mask), training = training)

class SelfAttention(tf.keras.layers.Layer):
	def __init__(self, MHA, **kwargs):
		super().__init__(**kwargs)
		self.MHA = MHA

	def call(self, x, mask = None):
		return self.MHA([x, x, x], mask = mask)

class AttentionLayer(tf.keras.layers.Layer):
	def __init__(self, n_heads = 8, FF_hidden = 512, activation = 'relu', **kwargs):
		super().__init__(**kwargs)
		self.n_heads = n_heads
		self.FF_hidden = FF_hidden
		self.activation = activation
		self.BN = tf.keras.layers.BatchNormalization(trainable = True)
		
	def build(self, input_shape):
		self.MHA_sublayer = ResidualBlock_BN(
			SelfAttention(
					MultiHeadAttention(n_heads = self.n_heads, embed_dim = input_shape[2])# input_shape[2] = embed_dim = 128	
			),
			self.BN
		)
		init = tf.keras.initializers.RandomUniform(minval = -1./tf.math.sqrt(tf.cast(input_shape[2], tf.float32)), maxval = 1./tf.math.sqrt(tf.cast(input_shape[2], tf.float32)))
		self.FF_sublayer = ResidualBlock_BN(
			tf.keras.models.Sequential([
					tf.keras.layers.Dense(self.FF_hidden, use_bias = True, activation = self.activation, kernel_initializer = init, bias_initializer = init),
					tf.keras.layers.Dense(input_shape[2], use_bias = True, kernel_initializer = init, bias_initializer = init)
			]),
			self.BN
		)
		super().build(input_shape)
	
	"""	def call
		arg x: (batch, n_nodes, embed_dim)
		return: (batch, n_nodes, embed_dim)
	"""
	def call(self, x, mask=None, training = True):
		return self.FF_sublayer(self.MHA_sublayer(x, mask = mask, training = training), training = training)

class GraphAttentionEncoder(tf.keras.models.Model):
	def __init__(self, embed_dim = 128, n_heads = 8, n_layers = 3, FF_hidden=512):
		super().__init__()
		init = tf.keras.initializers.RandomUniform(minval = -1./tf.math.sqrt(tf.cast(embed_dim, tf.float32)), maxval = 1./tf.math.sqrt(tf.cast(embed_dim, tf.float32)))
		self.init_W_depot = tf.keras.layers.Dense(embed_dim, use_bias = True, kernel_initializer = init, bias_initializer = init)# torch.nn.Linear(2, embedding_dim)
		self.init_W = tf.keras.layers.Dense(embed_dim, use_bias = True, kernel_initializer = init, bias_initializer = init)# torch.nn.Linear(3, embedding_dim)
		self.attention_layers = [AttentionLayer(n_heads, FF_hidden) for _ in range(n_layers)]
	
	@tf.function
	def call(self, x, mask = None, training = True):
		""" x[0] -- depot_xy: (batch, 2) --> embed_depot_xy: (batch, embed_dim)
			x[1] -- customer_xy: (batch, n_nodes-1, 2)
			x[2] -- demand: (batch, n_nodes-1)
			--> concated_customer_feature: (batch, n_nodes-1, 3) --> embed_customer_feature: (batch, n_nodes-1, embed_dim)
			embed_x(batch, n_nodes, embed_dim)
		"""
		x = tf.concat((self.init_W_depot(x[0])[:, None, :],
				self.init_W(tf.concat((x[1], x[2][:, :, None]), axis=-1))), axis = 1)
	
		for layer in self.attention_layers:
			x = layer(x, mask, training)# stack attention layers
		
		return (x, tf.reduce_mean(x, axis = 1))
		"""	(node embeddings(= embedding for all nodes), graph embedding(= mean of node embeddings for graph))
			=((batch, n_nodes, embed_dim), (batch, embed_dim))
		"""

if __name__ == '__main__':
	training = True
	K.set_learning_phase(training)
	encoder = GraphAttentionEncoder()
	dataset = generate_data()
	for i, data in enumerate(dataset.batch(5)):
		output = encoder(data, training = training)
		print(output[0])
		print(output[1])
		if i == 0:
			break
	encoder.summary()# available after buliding graph
	for w in encoder.trainable_weights:# non_trainable_weights:
		print(w.name)
	