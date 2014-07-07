#    This file is part of KTBS <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011-2012 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    KTBS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    KTBS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with KTBS.  If not, see <http://www.gnu.org/licenses/>.

"""
I provide a locking mechanism for resource that needs protection in the context of concurrency.

"""
import posix_ipc
from threading import current_thread
from contextlib import contextmanager
from rdfrest.local import _mark_as_deleted


def get_semaphore_name(resource_uri):
    """Return a safe semaphore name for a resource.

    :param basestring resource_uri: the URI of the resource.
    :return: safe semaphore name.
    :rtype: str
    """
    return str('/' + resource_uri.replace('/', '-'))


def reset_lock(resource_uri):
    """Reset the value of the semaphore to 1 for a given resource.

    :param basestring resource_uri: the URI of the resource that is possibly locked.

    .. note ::

        In some edge cases, this function can put the kTBS in a bad state. For example,
        the default lock value for a resource could be left to 2, removing the thread safety
        entirely for this resource.

        This could happen with the following scenario: a resource acquires a lock by
        calling :meth:`WithLockMixin.lock`, bringing the lock value to 0.
        In the same time, this function, :func:`reset_lock`, is called: it checks that
        the lock value is 0 and then bring it to 1.
        Then, the call to :meth:`WithLockMixin.lock` ends, releasing the lock:
        it brings the lock value from 1 to 2.

        As a result of having the lock value to 2, two calls to a method that needs a lock
        are not going to be run one after another. They will run at the same time, which
        defeats the purpose of using lock. This could lead to inconsistencies in the kTBS state.
    """
    semaphore = posix_ipc.Semaphore(name=get_semaphore_name(resource_uri),
                                    flags=posix_ipc.O_CREAT,
                                    initial_value=1)  # if the semaphore doesn't exist, set its value to 1
    if semaphore.value == 0:
        semaphore.release()
        semaphore.close()


class WithLockMixin(object):
    """ I provide methods to lock a resource.

    :cvar int __locking_thread_id: id of the thread
    :cvar LOCK_DEFAULT_TIMEOUT: how many seconds to wait for acquiring a lock on the resource.
    :type LOCK_DEFAULT_TIMEOUT: int or float
    """
    __locking_thread_id = None
    LOCK_DEFAULT_TIMEOUT = 60  # TODO take this variable from the global kTBS conf file

    def _get_semaphore(self):
        """Return the semaphore for this resource.

        We attempt to initialize the semaphore with a value of 1.
        However, if it already exists we don't change the semaphore value,
        but take it as is.

        :return: semaphore for this resource.
        :rtype: posix_ipc.Semaphore
        """
        return posix_ipc.Semaphore(name=get_semaphore_name(self.uri),
                                   flags=posix_ipc.O_CREAT,
                                   initial_value=1)

    @contextmanager
    def lock(self, resource, timeout=None):
        """Lock the current resource (self) with a semaphore.

        :param resource: the resource that asks for the lock.
        :param timeout: maximum time to wait on acquire() until a BusyError is raised.
        :type timeout: int or float
        :raise TypeError: if `resource` no longer exists.
        :raise posix_ipc.BusyError: if we fail to acquire the semaphore until timeout.
        """
        if timeout is None:
            timeout = self.LOCK_DEFAULT_TIMEOUT

        # If the current thread wants to access the locked resource it is good to go.
        # This should only happen when the thread wants to lock the resource further down the call stack.
        if self.__locking_thread_id == current_thread().ident:
            yield

        # Else, either another thread wants to access the resource (and it will wait until the lock is released),
        # or the current thread wants to access the resource and it is not locked yet.
        else:
            semaphore = self._get_semaphore()

            try:  # acquire the lock, re-raise BusyError with info if it fails
                semaphore.acquire(timeout)
                self.__locking_thread_id = current_thread().ident

                try:  # catch exceptions occurring after the lock has been acquired
                    # Make sure the resource still exists (it could have been deleted by a concurrent process).
                    if len(resource.state) == 0:
                        _mark_as_deleted(resource)
                        raise TypeError('The resource <{uri}> no longer exists.'.format(uri=resource.get_uri()))
                    yield

                finally:  # make sure we exit properly by releasing the lock
                    self.__locking_thread_id = None
                    semaphore.release()
                    semaphore.close()

            except posix_ipc.BusyError:
                thread_id = self.__locking_thread_id if self.__locking_thread_id else 'Unknown'
                error_msg = 'The resource <{res_uri}> is locked by thread {thread_id}.'.format(res_uri=self.uri,
                                                                                               thread_id=thread_id)
                raise posix_ipc.BusyError(error_msg)

    @contextmanager
    def edit(self, parameters=None, clear=None, _trust=False):
        """I override :meth:`rdfrest.interface.IResource.edit`.
        """
        with self.lock(self), super(WithLockMixin, self).edit(parameters, clear, _trust) as editable:
            yield editable

    def post_graph(self, graph, parameters=None,
                   _trust=False, _created=None, _rdf_type=None):
        """I override :meth:`rdfrest.mixins.GraphPostableMixin.post_graph`.
        """
        with self.lock(self):
            return super(WithLockMixin, self).post_graph(graph, parameters,
                                                         _trust, _created, _rdf_type)

    def delete(self, parameters=None, _trust=False):
        """I override :meth:`rdfrest.local.EditableResource.delete`.
        """
        root = self.get_root()
        with root.lock(self), self.lock(self):
            super(WithLockMixin, self).delete(parameters, _trust)

    def ack_delete(self, parameters):
        """I override :meth:`rdfrest.util.EditableResource.ack_delete`.
        """
        super(WithLockMixin, self).ack_delete(parameters)
        self._get_semaphore().unlink()  # remove the semaphore from this resource as it no longer exists

    @classmethod
    def create(cls, service, uri, new_graph):
        """ I am called when a :class:`KtbsRoot` or a :class:`Base` is created.
        After checking that the resource we create is correct, I set its lock to 1 because it is new
        resource so there is no reason for it to be locked.
        """
        super(WithLockMixin, cls).create(service, uri, new_graph)
        reset_lock(uri)
