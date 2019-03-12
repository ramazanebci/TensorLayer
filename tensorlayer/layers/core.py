#! /usr/bin/python
# -*- coding: utf-8 -*-

from abc import abstractmethod

import tensorflow as tf
import tensorlayer as tl

from tensorlayer.layers.utils import list_remove_repeat, get_variable_with_initializer

from tensorlayer import logging

from tensorlayer.decorators import deprecated_alias
from tensorlayer.decorators import protected_method
from tensorlayer.decorators import private_method

__all__ = [
    'Layer',
    'ModelLayer',
    'LayerList'
]

_global_layer_name_dict = {}  # TODO: better implementation?


def _addindent(s_, numSpaces):
    s = s_.split('\n')
    # don't do anything for single-line stuff
    if len(s) == 1:
        return s_
    first = s.pop(0)
    s = [(numSpaces * ' ') + line for line in s]
    s = '\n'.join(s)
    s = first + '\n' + s
    return s


class Layer(object):
    """The basic :class:`Layer` class represents a single layer of a neural network.

    It should be subclassed when implementing new types of layers.

    Parameters
    ----------
    name : str or None
        A unique layer name. If None, a unique name will be automatically assigned.

    Methods
    ---------
    __init__()
        Initializing the Layer.
    __call__()
        (1) Building the Layer if necessary. (2) Forwarding the computation.
    weights()
        Return a list of Tensor which are all trainable weights of this Layer.
    build()
        Abstract method. Build the Layer. All trainable weights should be defined in this function.
    forward()
        Abstract method. Forward computation and return computation results.

    """

    def __init__(self, name=None, *args, **kwargs):
        """
        Initializing the Layer.

        :param name: str or None
        """

        # FIXME : model save part @runhai
        # Layer constants
        # for key in kwargs.keys():
        #     setattr(self, key, self._argument_dict_checkup(kwargs[key]))

        # Auto naming if the name is not given
        global _global_layer_name_dict
        if name is None:
            prefix = self.__class__.__name__.lower()
            if _global_layer_name_dict.get(prefix) is not None:
                _global_layer_name_dict[prefix] += 1
                name = prefix + '_' + str(_global_layer_name_dict[prefix])
            else:
                _global_layer_name_dict[prefix] = 0
                name = prefix

        self.name = name

        # Layer building state
        self._built = False

        # Layer nodes state
        self._nodes = []
        self._nodes_fixed = False

        # Layer weight state
        self._weights = None

        # Layer training state
        self.is_train = True

        # FIXME : model save part @ruihai
        # self.add_prev = False
        # self.graph = {}
        # self.graph.update({'class': self.__class__.__name__.split('.')[-1]})
        # self.all_graphs = list()
        # self.layer_args = self._get_init_args(skip=3)
        # self.graph.update(self.layer_args)
        # if self.__class__.__name__ in tl.layers.inputs.__all__:
        #     self.graph.update({'prev_layer': None})
        #     self._add_graphs((self.name, self.graph))
        #     self.add_prev = True

    @staticmethod
    def _compute_shape(tensors):
        if isinstance(tensors, list):
            shape_mem = [t.get_shape().as_list() for t in tensors]
        else:
            shape_mem = tensors.get_shape().as_list()
        return shape_mem

    @property
    def weights(self):
        return self._weights

    def __call__(self, inputs, **kwargs):
        """
        (1) Build the Layer if necessary.
        (2) Forward the computation and return results.
        (3) Add LayerNode if necessary

        :param prev_layer: np.ndarray, Tensor, Layer, list of Layers
        :param kwargs:
        :return: Layer
        """
        if self.__class__.__name__ in tl.layers.inputs.__all__:
            input_tensors = tf.convert_to_tensor(inputs)
        else:
            input_tensors = inputs

        if not self._built:
            if isinstance(self, LayerList):
                self._input_tensors = input_tensors
            inputs_shape = self._compute_shape(input_tensors)
            self.build(inputs_shape)
            self._built = True

        outputs = self.forward(input_tensors, **kwargs)

        if not self._nodes_fixed:
            self._add_node(input_tensors, outputs)
        return outputs

    def _add_node(self, input_tensors, output_tensors):
        inputs_list = input_tensors if isinstance(input_tensors, list) else [input_tensors]
        outputs_list = output_tensors if isinstance(output_tensors, list) else [output_tensors]

        if self.__class__.__name__ in tl.layers.inputs.__all__:
            # for InputLayer, there should be no in_nodes
            in_nodes = []
        else:
            in_nodes = [tensor._info[0] for tensor in inputs_list]
        node_index = len(self._nodes)

        new_node = LayerNode(self, node_index, in_nodes, inputs_list, outputs_list)
        self._nodes.append(new_node)
        for idx, tensor in enumerate(outputs_list):
            tensor._info = (new_node, idx) # FIXME : modify tensor outside layers? how to deal?

    def _release_memory(self):
        """
        WARINING: This function should be called with great caution.

        self.inputs and self.outputs will be set as None but not deleted in order to release memory.
        """
        # FIXME : not understand why saving inputs/outputs shape
        for node in self._nodes:
            node.in_tensors = None
            node.out_tensors = None

    def _set_mode_for_layers(self, is_train):
        """ Set training/evaluation mode for the Layer"""
        self.is_train = is_train

    def _get_weights(self, var_name, shape, init=tl.initializers.random_normal()):
        """ Get trainable variables. """
        weight = get_variable_with_initializer(
            scope_name=self.name, var_name=var_name, shape=shape, init=init
        )
        if self._weights is None:
            self._weights = list()
        self._weights.append(weight)  # Add into the weight collection
        return weight

    @abstractmethod
    def build(self, inputs_shape):
        """
        An abstract method which should be overwritten in derived classes
        to define all necessary trainable weights of the layer.

        self.built should be set as True after self.build() is called.

        :param inputs_shape: tuple
        """
        raise Exception("The build(self, inputs_shape) method must be implemented by inherited class")

    @abstractmethod
    def forward(self, inputs):
        """
        An abstract method which should be overwritten in derived classes
        to define forward feeding operations of the layer.

        :param inputs: Tensor
        :return: Tensor
        """
        raise Exception("The forward method must be implemented by inherited class")

    @abstractmethod
    def __repr__(self):
        reprstr = "Layer"
        return reprstr

    def __setitem__(self, key, item):
        raise TypeError("The Layer API does not allow to use the method: `__setitem__`")

    def __delitem__(self, key):
        raise TypeError("The Layer API does not allow to use the method: `__delitem__`")

    # FIXME : model save part @ruihai
    # @protected_method
    # def _get_init_args(self, skip=3):
    #     """Get all arguments of current layer for saving the graph."""
    #     stack = inspect.stack()
    #
    #     if len(stack) < skip + 1:
    #         raise ValueError("The length of the inspection stack is shorter than the requested start position.")
    #
    #     args, _, _, values = inspect.getargvalues(stack[skip][0])
    #
    #     params = {}
    #
    #     for arg in args:
    #
    #         # some args dont need to be saved into the graph. e.g. the input placeholder
    #         if values[arg] is not None and arg not in ['self', 'prev_layer', 'inputs']:
    #
    #             val = values[arg]
    #
    #             # change function (e.g. act) into dictionary of module path and function name
    #             if inspect.isfunction(val):
    #                 params[arg] = {"module_path": val.__module__, "func_name": val.__name__}
    #             # ignore more args e.g. TF class
    #             elif arg.endswith('init'):
    #                 continue
    #             # for other data type, save them directly
    #             else:
    #                 params[arg] = val
    #
    #     return params
    #
    # @protected_method
    # def _add_graphs(self, graphs):
    #     if isinstance(graphs, list):
    #         self.all_graphs.extend(list(graphs))
    #     else:
    #         self.all_graphs.append(graphs)
    #
    # @private_method
    # def _argument_dict_checkup(self, args):
    #
    #     if not isinstance(args, dict) and args is not None:
    #         raise AssertionError(
    #             "One of the argument given to %s should be formatted as a dictionary" % self.__class__.__name__
    #         )
    #
    #     return args if args is not None else {}

class LayerNode(object):
    def __init__(self, layer, node_index, in_nodes, in_tensors, out_tensors):
        self.layer = layer
        self.node_index = node_index
        self.in_nodes = in_nodes
        self.out_nodes = []
        self.in_tensors = in_tensors
        self.out_tensors = out_tensors
        self.name = layer.name + "_node_{}".format(node_index)

    def __call__(self, inputs, **kwargs):
        outputs = self.layer.forward(inputs, **kwargs)
        self.in_tensors = inputs if isinstance(inputs, list) else [inputs]
        self.out_tensors = outputs if isinstance(outputs, list) else [outputs]
        return outputs


class ModelLayer(Layer):
    """
    The class :class:`ModelLayer` converts a :class:`Model` to a :class:`Layer` instance.

    Note that only a :class:`Model` with specified inputs and outputs can be converted to a :class:`ModelLayer`.
    For example, a customized model in dynamic eager mode normally does NOT have specified inputs and outputs so the
    customized model in dynamic eager mode can NOT be converted to a :class:`ModelLayer`.

    Parameters
    ----------
    model: tl.models.Model
        A model.
    name : str or None
        A unique layer name. If None, a unique name will be automatically assigned.

    Methods
    ---------
    __init__()
        Initializing the ModelLayer.
    weights()
        Same as the weights of the given model.
    build()
        Do nothing because the given model has already been built.
    forward()
        Forward the computation. Simply call the forward() of the given model.
    """

    def __init__(self, model, name=None):
        """
        Initializing the ModelLayer given a instance of Model.

        :param model:  tl.models.Model
        """
        super(ModelLayer, self).__init__(name=name)

        self.model = model

        # Layer input outputs
        # if isinstance(model.inputs, list):
        #     self.inputs = [t.outputs for t in model.inputs]
        # else:
        #     self.inputs = model.inputs.outputs
        #
        # self.outputs = model.forward(self.inputs)

        # self._input_layer = model.inputs

        # Layer building state
        self._built = True

        # Layer weight state
        self._weights = model.weights

        # Layer training state
        self.is_train = True

        logging.info(
            "ModelLayer %s from Model: %s" %
            (self.name, self.model.name)
        )

    def __repr__(self):
        tmpstr = 'ModelLayer' + '(\n'

        modstr = self.model.__repr__()
        modstr = _addindent(modstr, 2)

        tmpstr += modstr + ')'
        return tmpstr

    def build(self, inputs_shape):
        pass

    def forward(self, inputs):
        return self.model.forward(inputs)

    def _set_mode_for_layers(self, is_train):
        """ Set training/evaluation mode for the ModelLayer."""
        self.is_train = is_train
        return self.model._set_mode_for_layers(is_train)

    def _release_memory(self):
        """
        WARINING: This function should be called with great caution.

        self.inputs and self.outputs will be set as None but not deleted in order to release memory.
        """

        super(ModelLayer, self)._release_memory()
        self.model.release_memory()


class LayerList(Layer):
    """
    The class :class:`LayerList` is a linear stack of layers.

    The :class:`LayerList` can be created by passing a list of layer instances.
    The given layer instances will be automatically connected one by one.

    Parameters
    ----------
    layers: list of Layer
        A list of layers.
    name : str or None
        A unique layer name. If None, a unique name will be automatically assigned.

    Methods
    ---------
    __init__()
        Initializing the LayerList.
    weights()
        A collection of weights of all the layer instances.
    build()
        Build the LayerList. The layer instances will be connected automatically one by one.
    forward()
        Forward the computation. The computation will go through all layer instances.
    """

    def __init__(self, layers:list, name=None):
        """
        Initializing the LayerList given a list of Layer.

        :param layers: list of Layer
        :param name: str or None
        """

        super(LayerList, self).__init__(name=name)
        self.layers = layers

        is_built = True
        for layer in self.layers:
            if layer._built == False:
                is_built = False
            if layer._built == True and layer.weights is not None:
                # some layers in the list passed in have already been built
                # e.g. using input shape to construct layers in dynamic eager
                if self._weights == None:
                    self._weights = list()
                self._weights.extend(layer.weights)
        if is_built == True:
            self._built = True

        logging.info(
            "LayerList %s including layers [%s]" %
            (self.name, ', '.join([layer.name for layer in self.layers]))
        )

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return LayerList(list(self.layers)[idx])
        else:
            return self.layers[idx]

    def __len__(self):
        return len(self.layers)

    def __repr__(self):
        tmpstr = 'LayerList' + '(\n'
        for idx, layer in enumerate(self.layers):
            modstr = layer.__repr__()
            modstr = _addindent(modstr, 2)
            tmpstr = tmpstr + '  (' + str(idx) + '): ' + modstr + '\n'

        tmpstr = tmpstr + ')'
        return tmpstr

    def build(self, inputs_shape):
        """
        Build the LayerList. The layer instances will be connected automatically one by one.
        """
        in_tensor = self._input_tensors
        # in_layer = self._input_layer
        for layer in self.layers:
            is_build = layer._built
            out_tensor = layer(in_tensor)
            # nlayer = layer(in_layer)
            if is_build == False and layer.weights is not None:
                if self._weights == None:
                    self._weights = list()
                self._weights.extend(layer.weights)
            layer._built = True
            in_tensor = out_tensor
            # in_layer = nlayer

    def forward(self, inputs):
        """
        Forward the computation. The computation will go through all layer instances.
        """
        z = inputs
        for layer in self.layers:
            z = layer.forward(z)
        return z

    def _set_mode_for_layers(self, is_train):
        """Set training/evaluation mode for all layer instances."""
        self.is_train = is_train
        for layer in self.layers:
            if isinstance(layer, ModelLayer):
                layer._set_mode_for_layers(is_train)
            elif isinstance(layer, LayerList):
                layer._set_mode_for_layers(is_train)
            else:
                layer.is_train = is_train

    def _release_memory(self):
        """
        WARINING: This function should be called with great caution.

        self.inputs and self.outputs will be set as None but not deleted.
        """
        super(LayerList, self)._release_memory()
        for layer in self.layers:
            layer._release_memory()

