class MarketingSiteAPIClientException(Exception):
    pass


class MarketingSitePublisherException(Exception):
    pass


# Drupal Exceptions
class AliasCreateError(MarketingSitePublisherException):
    pass


class AliasDeleteError(MarketingSitePublisherException):
    pass


class FormRetrievalError(MarketingSitePublisherException):
    pass


class NodeCreateError(MarketingSitePublisherException):
    pass


class NodeDeleteError(MarketingSitePublisherException):
    pass


class NodeEditError(MarketingSitePublisherException):
    pass


class NodeLookupError(MarketingSitePublisherException):
    pass


class PersonToMarketingException(Exception):
    """ The exception thrown during the person adding process to marketing site """

    def __init__(self, message):
        super(PersonToMarketingException, self).__init__(message)
        suffix = 'The person data has not been saved. Please check your marketing site configuration'
        self.message = '{exception_msg} {suffix}'.format(exception_msg=message, suffix=suffix)

# Wordpress Exceptions
class PostLookupError(MarketingSitePublisherException):
    pass

class PostCreateError(MarketingSitePublisherException):
    pass

class PostEditError(MarketingSitePublisherException):
    pass

# class MediaLookupError(MarketingSitePublisherException):
#     pass
#
# class MediaCreateError(MarketingSitePublisherException):
#     pass
