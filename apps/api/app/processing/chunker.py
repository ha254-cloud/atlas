from itertools import islice


def chunked(iterable, size):

    iterator = iter(iterable)

    while True:
        batch = list(islice(iterator, size))

        if not batch:
            break

        yield batch
