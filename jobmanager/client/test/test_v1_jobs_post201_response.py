# coding: utf-8

"""
    Job Manager API

    API for managing jobs and builders within the Job Manager system.

    The version of the OpenAPI document: 1.0.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


import unittest
import datetime

from jobmanager_client.models.v1_jobs_post201_response import V1JobsPost201Response  # noqa: E501

class TestV1JobsPost201Response(unittest.TestCase):
    """V1JobsPost201Response unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional) -> V1JobsPost201Response:
        """Test V1JobsPost201Response
            include_option is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # uncomment below to create an instance of `V1JobsPost201Response`
        """
        model = V1JobsPost201Response()  # noqa: E501
        if include_optional:
            return V1JobsPost201Response(
                status_url = 'http://job-manager.internal/v1/jobs/123',
                maintenance = jobmanager_client.models._v1_jobs_post_201_response_maintenance._v1_jobs_post_201_response_maintenance(
                    kind = '', 
                    message = '', )
            )
        else:
            return V1JobsPost201Response(
        )
        """

    def testV1JobsPost201Response(self):
        """Test V1JobsPost201Response"""
        # inst_req_only = self.make_instance(include_optional=False)
        # inst_req_and_optional = self.make_instance(include_optional=True)

if __name__ == '__main__':
    unittest.main()
